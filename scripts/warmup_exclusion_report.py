#!/usr/bin/env python3
"""
Отчет об исключенных из прогрева сессиях

Показывает сколько сессий не участвуют в прогреве и по каким причинам
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from database import should_skip_warmup


def generate_report():
    """Генерирует отчет об исключенных сессиях"""
    
    conn = sqlite3.connect('data/sessions.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("\n")
    print("╔" + "═" * 98 + "╗")
    print("║" + " " * 25 + "WARMUP EXCLUSION REPORT" + " " * 50 + "║")
    print("╚" + "═" * 98 + "╝")
    print("\n")
    
    # Получить все аккаунты
    cursor.execute("SELECT * FROM accounts")
    all_accounts = [dict(row) for row in cursor.fetchall()]
    
    total = len(all_accounts)
    
    print(f"📊 ОБЩАЯ СТАТИСТИКА")
    print("=" * 100)
    print(f"Всего аккаунтов в базе: {total}")
    print()
    
    # Анализировать каждый аккаунт
    excluded = []
    included = []
    exclusion_reasons = {}
    
    for account in all_accounts:
        should_skip, reason = should_skip_warmup(account)
        if should_skip:
            excluded.append(account)
            exclusion_reasons[reason] = exclusion_reasons.get(reason, 0) + 1
        else:
            included.append(account)
    
    print(f"✅ Участвуют в прогреве: {len(included)} ({len(included)/total*100:.1f}%)")
    print(f"❌ Исключены из прогрева: {len(excluded)} ({len(excluded)/total*100:.1f}%)")
    print()
    
    # Детали по исключенным
    if excluded:
        print("=" * 100)
        print(f"❌ ИСКЛЮЧЕННЫЕ СЕССИИ - ДЕТАЛИ")
        print("=" * 100)
        print()
        
        # По причинам
        print("📋 По причинам исключения:")
        print()
        for reason, count in sorted(exclusion_reasons.items(), key=lambda x: x[1], reverse=True):
            percentage = count / len(excluded) * 100
            print(f"   • {reason}")
            print(f"     Количество: {count} ({percentage:.1f}% от исключенных)")
        print()
        
        # Детальный список
        print("=" * 100)
        print("📝 ДЕТАЛЬНЫЙ СПИСОК ИСКЛЮЧЕННЫХ СЕССИЙ")
        print("=" * 100)
        print()
        
        for i, account in enumerate(excluded, 1):
            should_skip, reason = should_skip_warmup(account)
            session_id = account.get('session_id', 'unknown')
            phone = account.get('phone_number', 'unknown')
            
            print(f"{i}. Session: {session_id}")
            print(f"   Phone: {phone}")
            print(f"   Reason: {reason}")
            print(f"   Flags: is_active={account.get('is_active')}, "
                  f"is_frozen={account.get('is_frozen')}, "
                  f"is_banned={account.get('is_banned')}, "
                  f"is_deleted={account.get('is_deleted')}, "
                  f"llm_disabled={account.get('llm_generation_disabled')}")
            if account.get('unban_date'):
                print(f"   Unban date: {account.get('unban_date')}")
            print()
    else:
        print("✅ Нет исключенных сессий - все активны!")
        print()
    
    # SQL статистика
    print("=" * 100)
    print("🔍 SQL СТАТИСТИКА")
    print("=" * 100)
    print()
    
    # По флагам
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) as inactive,
            SUM(CASE WHEN is_deleted = 1 THEN 1 ELSE 0 END) as deleted,
            SUM(CASE WHEN is_frozen = 1 THEN 1 ELSE 0 END) as frozen,
            SUM(CASE WHEN is_banned = 1 AND unban_date IS NULL THEN 1 ELSE 0 END) as banned_forever,
            SUM(CASE WHEN is_banned = 1 AND unban_date IS NOT NULL THEN 1 ELSE 0 END) as banned_temp,
            SUM(CASE WHEN llm_generation_disabled = 1 THEN 1 ELSE 0 END) as llm_disabled
        FROM accounts
    """)
    
    stats = cursor.fetchone()
    
    print(f"Неактивные (is_active=0):           {stats['inactive']}")
    print(f"Удаленные (is_deleted=1):           {stats['deleted']}")
    print(f"Замороженные (is_frozen=1):         {stats['frozen']}")
    print(f"Забанены навсегда (без unban_date): {stats['banned_forever']}")
    print(f"Временный бан (с unban_date):       {stats['banned_temp']} ✅ ГРЕЮТСЯ")
    print(f"LLM отключен вручную:                {stats['llm_disabled']}")
    print()
    
    # Экономия токенов
    print("=" * 100)
    print("💰 ЭКОНОМИЯ ТОКЕНОВ LLM")
    print("=" * 100)
    print()
    
    # Предположим среднее кол-во прогревов в день
    avg_daily_warmups = 4
    avg_tokens_per_plan = 2000  # примерная оценка
    
    tokens_saved_per_day = len(excluded) * avg_daily_warmups * avg_tokens_per_plan
    tokens_saved_per_month = tokens_saved_per_day * 30
    
    # Стоимость (DeepSeek: ~$0.14 per 1M tokens)
    cost_per_million = 0.14
    cost_saved_per_month = (tokens_saved_per_month / 1_000_000) * cost_per_million
    
    print(f"Исключено сессий: {len(excluded)}")
    print(f"Среднее кол-во прогревов/день: {avg_daily_warmups}")
    print(f"Среднее кол-во токенов на план: {avg_tokens_per_plan}")
    print()
    print(f"📉 Экономия токенов в день:   ~{tokens_saved_per_day:,}")
    print(f"📉 Экономия токенов в месяц:  ~{tokens_saved_per_month:,}")
    print(f"💵 Экономия $ в месяц:         ${cost_saved_per_month:.2f}")
    print()
    
    conn.close()
    
    print("=" * 100)
    print()


if __name__ == "__main__":
    generate_report()

