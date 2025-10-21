#!/usr/bin/env python3
"""
Проверка статуса аккаунтов - живые vs замороженные
"""

import sqlite3
import re

DATABASE_PATH = "data/sessions.db"
LOG_PATH = "logs/heat_up.log"

def check_status():
    """Проверяет статус всех аккаунтов"""
    
    # Анализируем логи
    with open(LOG_PATH, 'r') as f:
        lines = f.readlines()
    
    successful_updates = {}
    failed_frozen_updates = {}
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Ищем попытки update_profile
        if 'Updating profile for session' in line:
            match = re.search(r'session (\d+)', line)
            name_match = re.search(r'session \d+: ([^N]+?) (?:None|[А-Яа-я])', line)
            
            if match:
                session_id = match.group(1)
                name = name_match.group(1).strip() if name_match else "?"
                
                # Смотрим следующие строки
                success = False
                frozen = False
                
                for j in range(i+1, min(i+10, len(lines))):
                    next_line = lines[j]
                    
                    if 'ACTION SUCCEEDED' in next_line or 'Successfully updated profile' in next_line:
                        success = True
                        break
                    elif 'Session is frozen' in next_line or 'RPCSessionFrozen' in next_line:
                        frozen = True
                        break
                
                if success:
                    successful_updates[session_id] = name
                elif frozen:
                    failed_frozen_updates[session_id] = name
        
        i += 1
    
    # Получаем информацию из БД
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print()
    print("╔" + "═" * 98 + "╗")
    print("║" + " " * 30 + "📊 СТАТУС АККАУНТОВ" + " " * 48 + "║")
    print("╚" + "═" * 98 + "╝")
    print()
    
    if successful_updates:
        print("✅ ЖИВЫЕ АККАУНТЫ (могут обновлять профиль):")
        print("=" * 100)
        for session_id in sorted(successful_updates.keys()):
            cursor.execute("SELECT phone_number FROM accounts WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            phone = row['phone_number'] if row else "???"
            print(f"  ✅ Session {session_id} - {phone}")
        print()
        print(f"  ВСЕГО ЖИВЫХ: {len(successful_updates)}")
        print()
    
    if failed_frozen_updates:
        print("❄️  ЗАМОРОЖЕННЫЕ АККАУНТЫ (НЕ могут обновлять профиль):")
        print("=" * 100)
        for session_id in sorted(failed_frozen_updates.keys()):
            cursor.execute("SELECT phone_number FROM accounts WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            phone = row['phone_number'] if row else "???"
            print(f"  ❄️  Session {session_id} - {phone}")
        print()
        print(f"  ВСЕГО ЗАМОРОЖЕННЫХ: {len(failed_frozen_updates)}")
        print()
    
    total = len(successful_updates) + len(failed_frozen_updates)
    if total > 0:
        alive_percent = len(successful_updates) / total * 100
        frozen_percent = len(failed_frozen_updates) / total * 100
        
        print("=" * 100)
        print("📊 СТАТИСТИКА:")
        print("=" * 100)
        print(f"Всего аккаунтов: {total}")
        print(f"✅ Живых: {len(successful_updates)} ({alive_percent:.0f}%)")
        print(f"❄️  Замороженных: {len(failed_frozen_updates)} ({frozen_percent:.0f}%)")
        print()
        
        if len(successful_updates) > 0:
            print(f"✅ У вас есть {len(successful_updates)} рабочих аккаунтов")
        else:
            print("❌ Все аккаунты замороженные")
    
    print()
    
    conn.close()

if __name__ == "__main__":
    try:
        check_status()
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

