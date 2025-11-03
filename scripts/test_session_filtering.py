#!/usr/bin/env python3
"""
Тестирование системы фильтрации сессий

Проверяет что:
1. Замороженные сессии (is_frozen) не попадают в прогрев
2. Удаленные сессии (is_deleted) не попадают в прогрев
3. Сессии с баном навсегда (is_banned без unban_date) не попадают в прогрев
4. Сессии с отключенной генерацией LLM (llm_generation_disabled) не попадают в прогрев
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import should_skip_warmup, get_accounts_for_warmup, init_database
from datetime import datetime, timedelta


def test_should_skip_warmup():
    """Тестирование функции should_skip_warmup()"""
    
    print("=" * 100)
    print("🧪 Testing should_skip_warmup() function")
    print("=" * 100)
    
    test_cases = [
        {
            "name": "Normal active session",
            "account": {
                "is_active": True,
                "is_deleted": False,
                "is_frozen": False,
                "is_banned": False,
                "llm_generation_disabled": False
            },
            "expected_skip": False,
            "expected_reason": ""
        },
        {
            "name": "Deleted session",
            "account": {
                "is_active": True,
                "is_deleted": True,
                "is_frozen": False,
                "is_banned": False,
                "llm_generation_disabled": False
            },
            "expected_skip": True,
            "expected_reason": "session is deleted"
        },
        {
            "name": "Frozen session",
            "account": {
                "is_active": True,
                "is_deleted": False,
                "is_frozen": True,
                "is_banned": False,
                "llm_generation_disabled": False
            },
            "expected_skip": True,
            "expected_reason": "session is frozen"
        },
        {
            "name": "Banned forever (no unban_date)",
            "account": {
                "is_active": True,
                "is_deleted": False,
                "is_frozen": False,
                "is_banned": True,
                "unban_date": None,
                "llm_generation_disabled": False
            },
            "expected_skip": True,
            "expected_reason": "session is banned forever (no unban_date)"
        },
        {
            "name": "Temporarily banned (unban_date in future) - ALLOWED",
            "account": {
                "is_active": True,
                "is_deleted": False,
                "is_frozen": False,
                "is_banned": True,
                "unban_date": (datetime.utcnow() + timedelta(days=1)).isoformat(),
                "llm_generation_disabled": False
            },
            "expected_skip": False,
            "expected_reason": ""
        },
        {
            "name": "Ban expired (unban_date in past)",
            "account": {
                "is_active": True,
                "is_deleted": False,
                "is_frozen": False,
                "is_banned": True,
                "unban_date": (datetime.utcnow() - timedelta(days=1)).isoformat(),
                "llm_generation_disabled": False
            },
            "expected_skip": False,
            "expected_reason": ""
        },
        {
            "name": "LLM generation disabled",
            "account": {
                "is_active": True,
                "is_deleted": False,
                "is_frozen": False,
                "is_banned": False,
                "llm_generation_disabled": True
            },
            "expected_skip": True,
            "expected_reason": "LLM generation is manually disabled for this session"
        },
        {
            "name": "Inactive session",
            "account": {
                "is_active": False,
                "is_deleted": False,
                "is_frozen": False,
                "is_banned": False,
                "llm_generation_disabled": False
            },
            "expected_skip": True,
            "expected_reason": "session is not active"
        }
    ]
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n{i}. {test['name']}")
        print(f"   Account state: {test['account']}")
        
        should_skip, reason = should_skip_warmup(test['account'])
        
        # Проверка результата
        success = True
        
        if should_skip != test['expected_skip']:
            print(f"   ❌ FAILED: Expected skip={test['expected_skip']}, got skip={should_skip}")
            success = False
        
        if 'expected_reason_contains' in test:
            if test['expected_reason_contains'] not in reason:
                print(f"   ❌ FAILED: Expected reason to contain '{test['expected_reason_contains']}', got '{reason}'")
                success = False
        elif reason != test['expected_reason']:
            print(f"   ❌ FAILED: Expected reason='{test['expected_reason']}', got reason='{reason}'")
            success = False
        
        if success:
            print(f"   ✅ PASSED: skip={should_skip}, reason='{reason}'")
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 100)
    print(f"📊 Test Results: {passed} passed, {failed} failed out of {len(test_cases)} total")
    print("=" * 100)
    
    return failed == 0


def test_get_accounts_for_warmup():
    """Тестирование функции get_accounts_for_warmup()"""
    
    print("\n" + "=" * 100)
    print("🧪 Testing get_accounts_for_warmup() function")
    print("=" * 100)
    
    # Инициализировать БД
    init_database()
    
    # Получить аккаунты
    accounts = get_accounts_for_warmup()
    
    print(f"\n📋 Total accounts returned: {len(accounts)}")
    
    # Проверить что все возвращенные аккаунты проходят фильтры
    all_valid = True
    invalid_accounts = []
    
    for account in accounts:
        should_skip, reason = should_skip_warmup(account)
        if should_skip:
            all_valid = False
            invalid_accounts.append({
                "session_id": account.get("session_id"),
                "reason": reason
            })
    
    if all_valid:
        print("✅ All returned accounts are valid for warmup")
        
        # Показать статистику
        if accounts:
            print("\n📊 Account statistics:")
            print(f"   - Active: {sum(1 for a in accounts if a.get('is_active'))}")
            print(f"   - Frozen: {sum(1 for a in accounts if a.get('is_frozen'))}")
            print(f"   - Banned: {sum(1 for a in accounts if a.get('is_banned'))}")
            print(f"   - Deleted: {sum(1 for a in accounts if a.get('is_deleted'))}")
            print(f"   - LLM disabled: {sum(1 for a in accounts if a.get('llm_generation_disabled'))}")
    else:
        print(f"❌ Found {len(invalid_accounts)} invalid accounts:")
        for acc in invalid_accounts:
            print(f"   - Session {acc['session_id']}: {acc['reason']}")
    
    print("=" * 100)
    
    return all_valid


def main():
    """Запустить все тесты"""
    
    print("\n")
    print("╔" + "═" * 98 + "╗")
    print("║" + " " * 30 + "SESSION FILTERING TESTS" + " " * 45 + "║")
    print("╚" + "═" * 98 + "╝")
    print("\n")
    
    results = []
    
    # Тест 1: Функция should_skip_warmup
    test1_passed = test_should_skip_warmup()
    results.append(("should_skip_warmup()", test1_passed))
    
    # Тест 2: Функция get_accounts_for_warmup
    test2_passed = test_get_accounts_for_warmup()
    results.append(("get_accounts_for_warmup()", test2_passed))
    
    # Итоговый результат
    print("\n" + "=" * 100)
    print("🏁 FINAL RESULTS")
    print("=" * 100)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    all_passed = all(passed for _, passed in results)
    
    print("=" * 100)
    if all_passed:
        print("🎉 All tests PASSED!")
        return 0
    else:
        print("❌ Some tests FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
