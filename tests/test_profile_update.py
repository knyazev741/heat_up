"""
Test profile update functionality for session 27082
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

# Config
SESSION_ID = "27082"
API_BASE_URL = settings.telegram_api_base_url
API_TOKEN = settings.telegram_api_key


async def test_update_profile():
    """Test updating profile (first_name, last_name, bio) via raw invoke"""
    
    # Import helper functions
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from telegram_tl_helpers import make_update_profile_query, make_get_full_user_query
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        headers = {
            "Authorization": f"Bearer {API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        url = f"{API_BASE_URL}/api/external/sessions/{SESSION_ID}/rpc/invoke"
        
        # Test 1: Update first_name and last_name
        print("\n" + "="*60)
        print("TEST 1: Updating first_name and last_name")
        print("="*60)
        
        query_name = make_update_profile_query(
            first_name="Иван Test",
            last_name="Петров Test"
        )
        print(f"Query: {query_name}")
        
        payload_name = {
            "params": {
                "query": query_name,
                "retries": 5,
                "timeout": 30
            }
        }
        
        try:
            response = await client.post(url, json=payload_name, headers=headers)
            print(f"Status: {response.status_code}")
            result = response.json()
            print(f"Response: {json.dumps(result, ensure_ascii=False, indent=2)}")
            
            if result.get("success"):
                print("✅ Name update successful!")
            else:
                print(f"❌ Name update failed: {result.get('error')}")
        except Exception as e:
            print(f"❌ Error during name update: {str(e)}")
        
        # Wait a bit
        await asyncio.sleep(3)
        
        # Test 2: Update bio
        print("\n" + "="*60)
        print("TEST 2: Updating bio (about)")
        print("="*60)
        
        bio_text = f"Токарь из Челябинска. ТЕСТ ОБНОВЛЕН {datetime.now().strftime('%H:%M:%S')}"
        query_bio = make_update_profile_query(about=bio_text)
        print(f"Query: {query_bio}")
        
        payload_bio = {
            "params": {
                "query": query_bio,
                "retries": 5,
                "timeout": 30
            }
        }
        
        try:
            response = await client.post(url, json=payload_bio, headers=headers)
            print(f"Status: {response.status_code}")
            result = response.json()
            print(f"Response: {json.dumps(result, ensure_ascii=False, indent=2)}")
            
            if result.get("success"):
                print("✅ Bio update successful!")
            else:
                print(f"❌ Bio update failed: {result.get('error')}")
        except Exception as e:
            print(f"❌ Error during bio update: {str(e)}")
        
        # Test 3: Get current profile info to verify changes
        print("\n" + "="*60)
        print("TEST 3: Getting current profile info")
        print("="*60)
        
        query_info = make_get_full_user_query()
        print(f"Query: {query_info}")
        
        payload_info = {
            "params": {
                "query": query_info,
                "retries": 5,
                "timeout": 30
            }
        }
        
        try:
            response = await client.post(url, json=payload_info, headers=headers)
            print(f"Status: {response.status_code}")
            result = response.json()
            
            if result.get("success") and result.get("result"):
                # Try to extract user info
                full_user = result.get("result", {})
                users_list = full_user.get("users", [])
                if users_list:
                    user = users_list[0]
                    print(f"\n📋 Current Profile:")
                    print(f"  First Name: {user.get('first_name')}")
                    print(f"  Last Name: {user.get('last_name')}")
                    
                # Bio is in full_user.about
                about = full_user.get("full_user", {}).get("about", "")
                if about:
                    print(f"  Bio: {about}")
                
                print(f"\n✅ Profile info retrieved!")
                print(f"\nFull response: {json.dumps(result, ensure_ascii=False, indent=2)}")
            else:
                print(f"❌ Failed to get profile: {result.get('error')}")
        except Exception as e:
            print(f"❌ Error getting profile: {str(e)}")


async def test_session_info():
    """Get basic session info to check if session is accessible"""
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        headers = {
            "Authorization": f"Bearer {API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        print("\n" + "="*60)
        print("Checking session accessibility")
        print("="*60)
        
        url = f"{API_BASE_URL}/api/external/sessions/{SESSION_ID}"
        
        try:
            response = await client.get(url, headers=headers)
            print(f"Status: {response.status_code}")
            result = response.json()
            print(f"Session info: {json.dumps(result, ensure_ascii=False, indent=2)}")
            
            if response.status_code == 200:
                print("✅ Session accessible!")
                return True
            else:
                print("❌ Session not accessible")
                return False
        except Exception as e:
            print(f"❌ Error checking session: {str(e)}")
            return False


async def main():
    print("="*60)
    print(f"Profile Update Test for Session {SESSION_ID}")
    print(f"Timestamp: {datetime.now()}")
    print("="*60)
    
    # First check if session is accessible
    accessible = await test_session_info()
    
    if not accessible:
        print("\n⚠️ Session not accessible. Check API_TOKEN and API_BASE_URL")
        return
    
    # Run profile update tests
    await test_update_profile()
    
    print("\n" + "="*60)
    print("All tests completed!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())

