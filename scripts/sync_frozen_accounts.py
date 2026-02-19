#!/usr/bin/env python3
"""
Синхронизация статуса frozen аккаунтов с Admin API.
Деактивирует замороженные аккаунты чтобы они не получали warmup задачи.
"""

import asyncio
import sqlite3
import sys
sys.path.insert(0, '/root/heat_up')

from admin_api_client import AdminAPIClient
from datetime import datetime


async def sync_frozen_accounts():
    """Синхронизирует frozen статус из Admin API"""

    client = AdminAPIClient()
    conn = sqlite3.connect('/root/heat_up/data/sessions.db')
    cur = conn.cursor()

    try:
        # 1. Получаем все наши warmup аккаунты
        cur.execute('SELECT session_id, is_frozen, is_active FROM accounts WHERE account_type = "warmup" AND is_deleted = 0')
        our_accounts = {row[0]: {'is_frozen': row[1], 'is_active': row[2]} for row in cur.fetchall()}
        print(f"Our warmup accounts: {len(our_accounts)}")

        # 2. Проверяем каждый аккаунт в Admin API
        newly_frozen = []
        already_frozen = []
        unfrozen = []
        errors = []

        for session_id, local_status in our_accounts.items():
            try:
                session = await client.get_session_by_id(int(session_id))
                if session is None:
                    errors.append((session_id, "Not found in Admin API"))
                    continue

                admin_frozen = session.get('frozen', False)
                admin_deleted = session.get('deleted', False)

                # Если удалён в Admin API
                if admin_deleted:
                    cur.execute('UPDATE accounts SET is_deleted = 1, is_active = 0 WHERE session_id = ?', (session_id,))
                    errors.append((session_id, "Deleted in Admin API"))
                    continue

                # Синхронизируем frozen статус
                if admin_frozen and not local_status['is_frozen']:
                    # Новая заморозка — синхронизируем
                    cur.execute('''
                        UPDATE accounts
                        SET is_frozen = 1, is_active = 0
                        WHERE session_id = ?
                    ''', (session_id,))
                    newly_frozen.append(session_id)

                elif admin_frozen and local_status['is_frozen']:
                    # Уже frozen и у нас и в Admin API
                    # Убедимся что is_active = 0
                    if local_status['is_active']:
                        cur.execute('UPDATE accounts SET is_active = 0 WHERE session_id = ?', (session_id,))
                    already_frozen.append(session_id)

                elif not admin_frozen and local_status['is_frozen']:
                    # Был frozen, теперь нет — странно, но возможно
                    unfrozen.append(session_id)

            except Exception as e:
                errors.append((session_id, str(e)))

        conn.commit()

        # Отчёт
        print(f"\n=== SYNC RESULTS ===")
        print(f"Newly frozen (updated): {len(newly_frozen)}")
        print(f"Already frozen: {len(already_frozen)}")
        print(f"Unfrozen (in Admin API but frozen locally): {len(unfrozen)}")
        print(f"Errors: {len(errors)}")

        if newly_frozen:
            print(f"\nNewly frozen accounts:")
            for sid in newly_frozen[:20]:
                print(f"  - {sid}")
            if len(newly_frozen) > 20:
                print(f"  ... and {len(newly_frozen) - 20} more")

        if unfrozen:
            print(f"\nUnfrozen accounts (check manually):")
            for sid in unfrozen:
                print(f"  - {sid}")

        if errors:
            print(f"\nErrors:")
            for sid, err in errors[:10]:
                print(f"  - {sid}: {err}")

        # Финальная статистика
        cur.execute('SELECT COUNT(*) FROM accounts WHERE account_type = "warmup" AND is_frozen = 1')
        total_frozen = cur.fetchone()[0]

        cur.execute('SELECT COUNT(*) FROM accounts WHERE account_type = "warmup" AND is_active = 1 AND is_frozen = 0 AND is_deleted = 0')
        total_active = cur.fetchone()[0]

        print(f"\n=== FINAL STATUS ===")
        print(f"Total frozen warmup: {total_frozen}")
        print(f"Total active warmup: {total_active}")

    finally:
        await client.close()
        conn.close()


if __name__ == "__main__":
    asyncio.run(sync_frozen_accounts())
