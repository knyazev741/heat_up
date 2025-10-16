"""
Test profile update for session 27084 - Анна Ковалева
"""

import asyncio
import httpx
import json
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import settings
from telegram_tl_helpers import make_update_profile_query, make_get_full_user_query

# Config
SESSION_ID = "27084"
API_BASE_URL = settings.telegram_api_base_url
API_TOKEN = settings.telegram_api_key


async def get_current_profile():
    """Get current profile info"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        headers = {
            "Authorization": f"Bearer {API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        url = f"{API_BASE_URL}/api/external/sessions/{SESSION_ID}/rpc/invoke"
        
        query = make_get_full_user_query()
        payload = {
            "params": {
                "query": query,
                "retries": 5,
                "timeout": 30
            }
        }
        
        try:
            response = await client.post(url, json=payload, headers=headers)
            result = response.json()
            
            if result.get("success"):
                full_user = result.get("result", {})
                users_list = full_user.get("users", [])
                if users_list:
                    user = users_list[0]
                    about = full_user.get("full_user", {}).get("about", "")
                    
                    return {
                        "first_name": user.get("first_name"),
                        "last_name": user.get("last_name"),
                        "about": about,
                        "phone": user.get("phone")
                    }
            return None
        except Exception as e:
            print(f"❌ Error getting profile: {str(e)}")
            return None


async def update_profile(first_name=None, last_name=None, bio=None):
    """Update profile"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        headers = {
            "Authorization": f"Bearer {API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        url = f"{API_BASE_URL}/api/external/sessions/{SESSION_ID}/rpc/invoke"
        
        query = make_update_profile_query(
            first_name=first_name,
            last_name=last_name,
            about=bio
        )
        
        payload = {
            "params": {
                "query": query,
                "retries": 5,
                "timeout": 30
            }
        }
        
        try:
            response = await client.post(url, json=payload, headers=headers)
            result = response.json()
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}


async def main():
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    print("="*70)
    print(f"🧪 TEST: Profile Update для сессии {SESSION_ID} (Анна Ковалева)")
    print(f"⏰ Время: {timestamp}")
    print("="*70)
    
    # Step 1: Get current profile
    print("\n📋 Шаг 1: Получаем текущий профиль...")
    current = await get_current_profile()
    
    if current:
        print(f"✅ Текущий профиль:")
        print(f"   Имя: {current['first_name']} {current['last_name']}")
        print(f"   Телефон: {current['phone']}")
        print(f"   Био: {current['about'][:80]}..." if current['about'] else "   Био: (пусто)")
    else:
        print("❌ Не удалось получить текущий профиль")
        return
    
    # Step 2: Update name
    print("\n🔄 Шаг 2: Обновляем имя на 'Анна ТЕСТ'...")
    result = await update_profile(
        first_name="Анна ТЕСТ",
        last_name="Ковалева TEST"
    )
    
    if result.get("success"):
        print(f"✅ Имя обновлено успешно!")
        if result.get("result"):
            user = result["result"].get("_", "")
            print(f"   Ответ Telegram: {user}")
    else:
        error = result.get("error", "Unknown error")
        print(f"❌ Ошибка обновления имени: {error}")
        if "frozen" in error.lower():
            print("   ⚠️ Сессия заморожена!")
            return
    
    await asyncio.sleep(3)
    
    # Step 3: Update bio
    print(f"\n🔄 Шаг 3: Обновляем био с тестовой меткой {timestamp}...")
    test_bio = f"Дизайнер ландшафтов из Екатеринбурга. Тест обновления {timestamp} ✅"
    
    result = await update_profile(bio=test_bio)
    
    if result.get("success"):
        print(f"✅ Био обновлено успешно!")
    else:
        error = result.get("error", "Unknown error")
        print(f"❌ Ошибка обновления био: {error}")
    
    await asyncio.sleep(3)
    
    # Step 4: Verify changes
    print("\n🔍 Шаг 4: Проверяем изменения...")
    updated = await get_current_profile()
    
    if updated:
        print(f"✅ Обновленный профиль:")
        print(f"   Имя: {updated['first_name']} {updated['last_name']}")
        print(f"   Био: {updated['about']}")
        
        # Compare
        print("\n📊 Сравнение:")
        if updated['first_name'] != current['first_name']:
            print(f"   ✅ Имя изменено: {current['first_name']} → {updated['first_name']}")
        else:
            print(f"   ⚠️ Имя НЕ изменилось: {current['first_name']}")
            
        if updated['last_name'] != current['last_name']:
            print(f"   ✅ Фамилия изменена: {current['last_name']} → {updated['last_name']}")
        else:
            print(f"   ⚠️ Фамилия НЕ изменилась: {current['last_name']}")
            
        if updated['about'] != current['about']:
            print(f"   ✅ Био изменено!")
            print(f"      Было: {current['about'][:50]}...")
            print(f"      Стало: {updated['about'][:50]}...")
        else:
            print(f"   ⚠️ Био НЕ изменилось")
    else:
        print("❌ Не удалось получить обновленный профиль")
    
    print("\n" + "="*70)
    print("🏁 Тест завершен!")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())

