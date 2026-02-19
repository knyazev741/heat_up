#!/usr/bin/env python3
"""
Аккуратная проверка всех warmup сессий через Admin API.
Проверяет каждую сессию с рандомной задержкой 8-12 секунд.
"""

import asyncio
import sqlite3
import sys
import random
from datetime import datetime

sys.path.insert(0, '/root/heat_up')

from admin_api_client import AdminAPIClient


async def check_all_sessions():
    """Проверяет все warmup сессии"""

    conn = sqlite3.connect('/root/heat_up/data/sessions.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Получаем все warmup сессии (включая frozen, чтобы проверить актуальность)
    cur.execute('''
        SELECT id, session_id, phone_number, is_frozen, is_active, is_deleted, warmup_stage
        FROM accounts
        WHERE account_type = 'warmup'
        ORDER BY session_id
    ''')
    accounts = cur.fetchall()

    print(f"=== CHECKING {len(accounts)} WARMUP SESSIONS ===")
    print(f"Started at: {datetime.now().isoformat()}\n")

    client = AdminAPIClient()

    results = {
        'ok': [],           # status=0, not frozen, not deleted (GOOD!)
        'busy': [],         # status=1 (sending broadcasts)
        'banned': [],       # status=2 (BANNED!)
        'frozen': [],       # frozen=True
        'deleted': [],      # deleted=True or not found
        'errors': []        # API errors
    }

    try:
        for i, acc in enumerate(accounts):
            session_id = acc['session_id']
            local_frozen = acc['is_frozen']
            local_active = acc['is_active']

            print(f"[{i+1}/{len(accounts)}] Checking session {session_id}...", end=" ", flush=True)

            try:
                # Пробуем получить сессию напрямую по ID
                session = await client.get_session_by_id(int(session_id))

                if session is None:
                    print(f"NOT FOUND in Admin API!")
                    results['deleted'].append({
                        'session_id': session_id,
                        'phone': acc['phone_number'],
                        'reason': 'Not found in Admin API'
                    })
                    # Помечаем как удалённую
                    cur.execute('UPDATE accounts SET is_deleted = 1, is_active = 0 WHERE session_id = ?', (session_id,))
                    continue

                admin_frozen = session.get('frozen', False)
                admin_deleted = session.get('deleted', False)
                admin_status = session.get('status')

                status_str = f"status={admin_status}, frozen={admin_frozen}, deleted={admin_deleted}"
                print(status_str)

                if admin_deleted:
                    results['deleted'].append({
                        'session_id': session_id,
                        'phone': acc['phone_number'],
                        'reason': 'Deleted in Admin API'
                    })
                    cur.execute('UPDATE accounts SET is_deleted = 1, is_active = 0 WHERE session_id = ?', (session_id,))

                elif admin_frozen:
                    results['frozen'].append({
                        'session_id': session_id,
                        'phone': acc['phone_number'],
                        'status': admin_status
                    })
                    cur.execute('UPDATE accounts SET is_frozen = 1, is_active = 0 WHERE session_id = ?', (session_id,))

                elif admin_status == 0:
                    # status=0 — НОРМАЛЬНЫЙ активный аккаунт!
                    results['ok'].append({
                        'session_id': session_id,
                        'phone': acc['phone_number'],
                        'status': 0
                    })
                    # Убеждаемся что локально активен
                    if local_frozen or not local_active:
                        cur.execute('UPDATE accounts SET is_frozen = 0, is_active = 1 WHERE session_id = ?', (session_id,))
                        print(f"  ^ Fixed local status (was frozen={local_frozen}, active={local_active})")

                elif admin_status == 1:
                    # status=1 — сессия В РАБОТЕ (шлёт рассылки)
                    results['busy'].append({
                        'session_id': session_id,
                        'phone': acc['phone_number']
                    })
                    print(f"  📤 Session is BUSY (sending broadcasts)")

                elif admin_status == 2:
                    # status=2 — БАН!
                    results['banned'].append({
                        'session_id': session_id,
                        'phone': acc['phone_number']
                    })
                    # Деактивируем
                    cur.execute('UPDATE accounts SET is_active = 0, is_banned = 1 WHERE session_id = ?', (session_id,))
                    print(f"  🚫 Session is BANNED (status=2)")

            except Exception as e:
                print(f"ERROR: {e}")
                results['errors'].append({
                    'session_id': session_id,
                    'phone': acc['phone_number'],
                    'error': str(e)
                })

            # Коммитим после каждой проверки
            conn.commit()

            # Рандомная задержка 8-12 секунд (кроме последней)
            if i < len(accounts) - 1:
                delay = random.uniform(8, 12)
                print(f"  Waiting {delay:.1f}s...")
                await asyncio.sleep(delay)

    finally:
        await client.close()
        conn.close()

    # Итоговый отчёт
    print("\n" + "=" * 60)
    print("=== FINAL REPORT ===")
    print(f"Finished at: {datetime.now().isoformat()}\n")

    print(f"✅ OK (status=0, ready): {len(results['ok'])}")
    print(f"📤 BUSY (status=1, sending broadcasts): {len(results['busy'])}")
    print(f"🚫 BANNED (status=2): {len(results['banned'])}")
    print(f"❄️  FROZEN: {len(results['frozen'])}")
    print(f"🗑️  DELETED/NOT FOUND: {len(results['deleted'])}")
    print(f"❌ ERRORS: {len(results['errors'])}")

    if results['frozen']:
        print(f"\n--- FROZEN SESSIONS ({len(results['frozen'])}) ---")
        for s in results['frozen'][:20]:
            print(f"  {s['session_id']}: {s['phone']}")
        if len(results['frozen']) > 20:
            print(f"  ... and {len(results['frozen']) - 20} more")

    if results['deleted']:
        print(f"\n--- DELETED SESSIONS ({len(results['deleted'])}) ---")
        for s in results['deleted'][:20]:
            print(f"  {s['session_id']}: {s['phone']} - {s['reason']}")
        if len(results['deleted']) > 20:
            print(f"  ... and {len(results['deleted']) - 20} more")

    if results['busy']:
        print(f"\n--- BUSY SESSIONS (status=1) ({len(results['busy'])}) ---")
        for s in results['busy'][:10]:
            print(f"  {s['session_id']}: {s['phone']}")

    if results['banned']:
        print(f"\n--- BANNED SESSIONS (status=2) ({len(results['banned'])}) ---")
        for s in results['banned'][:20]:
            print(f"  {s['session_id']}: {s['phone']}")

    if results['errors']:
        print(f"\n--- ERRORS ({len(results['errors'])}) ---")
        for s in results['errors']:
            print(f"  {s['session_id']}: {s['error']}")

    return results


if __name__ == "__main__":
    results = asyncio.run(check_all_sessions())
