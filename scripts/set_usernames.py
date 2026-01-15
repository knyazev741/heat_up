#!/usr/bin/env python3
"""Set usernames for Ukrainian accounts"""
import asyncio
import httpx
import sys
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import settings
from telegram_tl_helpers import make_update_username_query

API_BASE = settings.telegram_api_base_url
API_KEY = settings.telegram_api_key


async def set_username_via_invoke(session_id: int, username: str):
    """Set username via invoke raw TL method"""
    url = f"{API_BASE}/api/external/sessions/{session_id}/rpc/invoke"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    query = make_update_username_query(username)

    payload = {
        "params": {
            "query": query,
            "retries": 3,
            "timeout": 30
        }
    }

    print(f"Setting username '{username}' for session {session_id} via invoke...")
    print(f"API: {API_BASE}")
    print(f"Query: {query[:100]}...")

    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print(f"Response: {result}")
                return result
            else:
                print(f"Error response: {response.text[:300]}")
                return None
        except httpx.ReadTimeout as e:
            print(f"Timeout: {e}")
            return None
        except Exception as e:
            print(f"Error: {type(e).__name__}: {e}")
            return None


async def main():
    # Two Ukrainian warmup accounts with status 0 (active in local DB)
    # session_id = Admin API ID
    accounts = [
        (27161, "vlad_kyiv_98"),
        (27163, "maryna_odesa_23"),
    ]

    results = []
    for session_id, username in accounts:
        result = await set_username_via_invoke(session_id, username)
        success = result and result.get("success")
        results.append((session_id, username, success))
        print("-" * 50)

    print("\n=== SUMMARY ===")
    for session_id, username, success in results:
        status = "✅" if success else "❌"
        print(f"{status} Session {session_id}: @{username}")


if __name__ == "__main__":
    asyncio.run(main())
