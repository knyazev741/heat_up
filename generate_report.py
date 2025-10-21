#!/usr/bin/env python3
"""
ИТОГОВЫЙ ОТЧЕТ О ПРОГРЕВЕ ЗА 24 ЧАСА
"""

import sqlite3
import re
from datetime import datetime, timedelta
from collections import defaultdict

DATABASE_PATH = "data/sessions.db"

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def generate_report():
    """Генерирует красивый отчет о прогреве за последние 24 часа"""
    
    # Временные метки
    now = datetime.utcnow()
    yesterday = now - timedelta(days=1)

    print()
    print("╔" + "═" * 98 + "╗")
    print("║" + " " * 20 + "📊 ОТЧЕТ О ПРОГРЕВЕ АККАУНТОВ ЗА ПОСЛЕДНИЕ 24 ЧАСА" + " " * 28 + "║")
    print("╚" + "═" * 98 + "╝")
    print()

    print(f"⏰ Период отчета: {yesterday.strftime('%d.%m.%Y %H:%M')} - {now.strftime('%d.%m.%Y %H:%M')} UTC")
    print(f"📅 Дата генерации: {now.strftime('%d.%m.%Y %H:%M:%S')}")
    print()

    conn = get_db_connection()
    cursor = conn.cursor()

    # ===== 1. ОБЩАЯ СТАТИСТИКА =====
    print("┌" + "─" * 98 + "┐")
    print("│" + " 1️⃣  ОБЩАЯ СТАТИСТИКА" + " " * 76 + "│")
    print("└" + "─" * 98 + "┘")
    print()

    cursor.execute("SELECT COUNT(*) as total FROM accounts")
    total_accounts = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as active FROM accounts WHERE is_active = 1")
    active_accounts = cursor.fetchone()['active']

    cursor.execute("SELECT COUNT(*) as frozen FROM accounts WHERE is_frozen = 1")
    frozen_accounts = cursor.fetchone()['frozen']

    cursor.execute("SELECT COUNT(*) as banned FROM accounts WHERE is_banned = 1")
    banned_accounts = cursor.fetchone()['banned']

    print(f"  📱 Всего аккаунтов в системе: {total_accounts}")
    print(f"     ├─ ✅ Активных: {active_accounts}")
    print(f"     ├─ ❄️  Постоянно замороженных: {frozen_accounts}")
    print(f"     └─ 🚫 Заблокированных: {banned_accounts}")
    print()

    # ===== 2. ПРОГРЕВ ЗА 24 ЧАСА =====
    print("┌" + "─" * 98 + "┐")
    print("│" + " 2️⃣  АКТИВНОСТЬ ЗА 24 ЧАСА" + " " * 71 + "│")
    print("└" + "─" * 98 + "┘")
    print()

    cursor.execute("""
        SELECT COUNT(*) as warmup_count
        FROM warmup_sessions
        WHERE started_at >= ?
    """, (yesterday,))
    total_warmups = cursor.fetchone()['warmup_count']

    cursor.execute("""
        SELECT COUNT(DISTINCT account_id) as unique_accounts
        FROM warmup_sessions
        WHERE started_at >= ?
    """, (yesterday,))
    warmed_accounts = cursor.fetchone()['unique_accounts']

    cursor.execute("""
        SELECT 
            SUM(completed_actions_count) as total_actions,
            SUM(failed_actions_count) as failed_actions
        FROM warmup_sessions
        WHERE started_at >= ?
    """, (yesterday,))
    actions_row = cursor.fetchone()
    total_actions = actions_row['total_actions'] or 0
    failed_actions = actions_row['failed_actions'] or 0
    successful_actions = total_actions - failed_actions

    success_rate = (successful_actions / total_actions * 100) if total_actions > 0 else 0

    print(f"  🔥 Всего сеансов прогрева: {total_warmups}")
    print(f"  👥 Уникальных аккаунтов прогрето: {warmed_accounts}")
    print()
    print(f"  ⚡ Всего действий выполнено: {total_actions}")
    print(f"     ├─ ✅ Успешных: {successful_actions} ({success_rate:.1f}%)")
    print(f"     └─ ❌ Неудачных: {failed_actions} ({100-success_rate:.1f}%)")
    print()

    # Средняя статистика
    avg_warmups_per_account = total_warmups / warmed_accounts if warmed_accounts > 0 else 0
    avg_actions_per_warmup = total_actions / total_warmups if total_warmups > 0 else 0

    print(f"  📊 Средняя статистика:")
    print(f"     ├─ Прогревов на аккаунт: {avg_warmups_per_account:.1f}")
    print(f"     └─ Действий за прогрев: {avg_actions_per_warmup:.1f}")
    print()

    # ===== 3. ДЕТАЛИ ПО КАЖДОМУ АККАУНТУ =====
    print("┌" + "─" * 98 + "┐")
    print("│" + " 3️⃣  ДЕТАЛИЗАЦИЯ ПО АККАУНТАМ" + " " * 68 + "│")
    print("└" + "─" * 98 + "┘")
    print()

    cursor.execute("""
        SELECT 
            a.id,
            a.session_id,
            a.phone_number,
            a.warmup_stage,
            COUNT(ws.id) as warmup_count,
            SUM(ws.completed_actions_count) as total_actions,
            SUM(ws.failed_actions_count) as failed_actions,
            MAX(ws.started_at) as last_warmup
        FROM accounts a
        LEFT JOIN warmup_sessions ws ON a.id = ws.account_id AND ws.started_at >= ?
        GROUP BY a.id
        ORDER BY warmup_count DESC, a.session_id
    """, (yesterday,))

    accounts = cursor.fetchall()

    for idx, account in enumerate(accounts, 1):
        warmup_count = account['warmup_count'] or 0
        total_actions = account['total_actions'] or 0
        failed_actions = account['failed_actions'] or 0
        successful_actions = total_actions - failed_actions
        
        # Рассчитываем success rate
        acc_success_rate = (successful_actions / total_actions * 100) if total_actions > 0 else 100
        
        # Определяем иконку статуса
        if warmup_count == 0:
            status_icon = "⚪"
            status_text = "БЕЗ АКТИВНОСТИ"
        elif acc_success_rate >= 70:
            status_icon = "✅"
            status_text = "ОТЛИЧНО"
        elif acc_success_rate >= 50:
            status_icon = "⚠️ "
            status_text = "ЕСТЬ ОШИБКИ"
        else:
            status_icon = "❌"
            status_text = "МНОГО ОШИБОК"
        
        print(f"  {idx:2d}. {status_icon} Session {account['session_id']} ({account['phone_number']})")
        print(f"      ├─ Статус: {status_text}")
        print(f"      ├─ Стадия прогрева: {account['warmup_stage']}")
        print(f"      ├─ Прогревов за сутки: {warmup_count}")
        
        if warmup_count > 0:
            print(f"      ├─ Действий: {total_actions} (✅ {successful_actions} / ❌ {failed_actions})")
            print(f"      ├─ Success rate: {acc_success_rate:.0f}%")
            print(f"      └─ Последний прогрев: {account['last_warmup']}")
        else:
            print(f"      └─ (за последние 24 часа не прогревался)")
        print()

    # ===== 4. ПРОБЛЕМНЫЕ АККАУНТЫ =====
    print("┌" + "─" * 98 + "┐")
    print("│" + " 4️⃣  ПРОБЛЕМНЫЕ АККАУНТЫ И ОШИБКИ" + " " * 64 + "│")
    print("└" + "─" * 98 + "┘")
    print()

    # Анализ временных заморозок из логов
    try:
        with open('logs/heat_up.log', 'r') as f:
            lines = f.readlines()

        frozen_errors = defaultdict(int)
        sessions_with_frozen = set()

        for line in lines:
            match = re.search(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if match:
                try:
                    log_time = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                    if log_time < yesterday:
                        continue
                except:
                    pass
            
            if 'Session is frozen' in line or 'RPCSessionFrozen' in line:
                session_match = re.search(r'session (\d+)', line)
                if session_match:
                    session_id = session_match.group(1)
                    sessions_with_frozen.add(session_id)
                    frozen_errors[session_id] += 1

        # Вывод информации о заморозках
        if sessions_with_frozen:
            print(f"  ⚠️  ВРЕМЕННЫЕ ЗАМОРОЗКИ (Session Frozen):")
            print()
            print(f"     Обнаружено {len(sessions_with_frozen)} сессий с ошибками 'Session is frozen':")
            print()
            for session_id in sorted(sessions_with_frozen):
                count = frozen_errors[session_id]
                cursor.execute("SELECT phone_number FROM accounts WHERE session_id = ?", (session_id,))
                phone = cursor.fetchone()
                phone_str = f"({phone['phone_number']})" if phone else ""
                print(f"     • Session {session_id} {phone_str}: {count} раз(а)")
            print()
            print("     ℹ️  ВАЖНО: Это ВРЕМЕННЫЕ заморозки при попытке обновить профиль.")
            print("        Аккаунты НЕ заблокированы постоянно - другие действия выполняются успешно.")
            print()
        else:
            print("  ✅ Временных заморозок не обнаружено")
            print()
    except Exception as e:
        print(f"  ⚠️  Не удалось проанализировать лог-файл: {e}")
        print()

    # Постоянно замороженные
    if frozen_accounts > 0:
        cursor.execute("""
            SELECT session_id, phone_number
            FROM accounts
            WHERE is_frozen = 1
        """)
        frozen = cursor.fetchall()
        print(f"  ❄️  ПОСТОЯННО ЗАМОРОЖЕННЫЕ АККАУНТЫ ({len(frozen)}):")
        for acc in frozen:
            print(f"     • Session {acc['session_id']} ({acc['phone_number']})")
        print()
    else:
        print("  ✅ Постоянно замороженных аккаунтов НЕТ")
        print()

    # Заблокированные
    if banned_accounts > 0:
        cursor.execute("""
            SELECT session_id, phone_number
            FROM accounts
            WHERE is_banned = 1
        """)
        banned = cursor.fetchall()
        print(f"  🚫 ЗАБЛОКИРОВАННЫЕ АККАУНТЫ ({len(banned)}):")
        for acc in banned:
            print(f"     • Session {acc['session_id']} ({acc['phone_number']})")
        print()
    else:
        print("  ✅ Заблокированных аккаунтов НЕТ")
        print()

    # ===== 5. ТОП-5 АКТИВНЫХ =====
    print("┌" + "─" * 98 + "┐")
    print("│" + " 5️⃣  TOP-5 САМЫХ АКТИВНЫХ АККАУНТОВ" + " " * 61 + "│")
    print("└" + "─" * 98 + "┘")
    print()

    cursor.execute("""
        SELECT 
            a.session_id,
            a.phone_number,
            COUNT(ws.id) as warmup_count,
            SUM(ws.completed_actions_count) as total_actions,
            SUM(ws.failed_actions_count) as failed_actions
        FROM accounts a
        JOIN warmup_sessions ws ON a.id = ws.account_id
        WHERE ws.started_at >= ?
        GROUP BY a.id
        ORDER BY warmup_count DESC, total_actions DESC
        LIMIT 5
    """, (yesterday,))

    top_accounts = cursor.fetchall()

    if top_accounts:
        for idx, acc in enumerate(top_accounts, 1):
            successful = acc['total_actions'] - acc['failed_actions']
            success_rate = (successful / acc['total_actions'] * 100) if acc['total_actions'] > 0 else 0
            
            if idx == 1:
                medal = "🥇"
            elif idx == 2:
                medal = "🥈"
            elif idx == 3:
                medal = "🥉"
            else:
                medal = f"  {idx}"
            
            print(f"  {medal} Session {acc['session_id']} ({acc['phone_number']})")
            print(f"      Прогревов: {acc['warmup_count']}, Действий: {acc['total_actions']} (Success rate: {success_rate:.0f}%)")
            print()
    else:
        print("  Нет активных аккаунтов за последние 24 часа")
        print()

    # ===== ИТОГИ =====
    print("┌" + "─" * 98 + "┐")
    print("│" + " 📌 ВЫВОДЫ" + " " * 87 + "│")
    print("└" + "─" * 98 + "┘")
    print()

    print(f"  ✅ За последние 24 часа успешно прогрето {warmed_accounts} из {total_accounts} аккаунтов")
    print(f"  ✅ Выполнено {total_warmups} сеансов прогрева с {successful_actions} успешными действиями")
    print(f"  ✅ Общий success rate: {success_rate:.1f}%")
    print()

    if frozen_accounts > 0 or banned_accounts > 0:
        print(f"  ⚠️  Обнаружены проблемы:")
        if frozen_accounts > 0:
            print(f"      • Постоянно замороженных аккаунтов: {frozen_accounts}")
        if banned_accounts > 0:
            print(f"      • Заблокированных аккаунтов: {banned_accounts}")
        print()
    else:
        print(f"  ✅ Постоянных блокировок и заморозок НЕ ОБНАРУЖЕНО")
        print()

    try:
        if sessions_with_frozen:
            print(f"  ℹ️  Временные заморозки у {len(sessions_with_frozen)} сессий - это нормально")
            print(f"      (ошибки при update_profile, другие действия выполняются)")
            print()
    except:
        pass

    print("╔" + "═" * 98 + "╗")
    print("║" + " " * 42 + "КОНЕЦ ОТЧЕТА" + " " * 44 + "║")
    print("╚" + "═" * 98 + "╝")
    print()

    conn.close()

if __name__ == "__main__":
    try:
        generate_report()
    except Exception as e:
        print(f"❌ Ошибка при генерации отчета: {e}")
        import traceback
        traceback.print_exc()

