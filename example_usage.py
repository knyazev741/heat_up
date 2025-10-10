"""
Example usage script for Heat Up service
"""

import asyncio
import httpx
import sys


async def warmup_session_async(session_id: str, base_url: str = "http://localhost:8080"):
    """
    Example: Warmup session asynchronously (returns immediately)
    """
    print(f"🔥 Starting async warmup for session: {session_id}")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{base_url}/warmup/{session_id}",
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
            print(f"✅ Warmup initiated!")
            print(f"📋 Action plan ({len(result['action_plan'])} actions):")
            for i, action in enumerate(result['action_plan'], 1):
                print(f"  {i}. {action['action']} - {action.get('reason', 'N/A')}")
            
            return result
            
        except httpx.HTTPStatusError as e:
            print(f"❌ HTTP Error: {e.response.status_code}")
            print(f"   {e.response.text}")
        except Exception as e:
            print(f"❌ Error: {str(e)}")


async def warmup_session_sync(session_id: str, base_url: str = "http://localhost:8080"):
    """
    Example: Warmup session synchronously (waits for completion)
    """
    print(f"🔥 Starting sync warmup for session: {session_id}")
    print("⏳ This will wait for all actions to complete...\n")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{base_url}/warmup-sync/{session_id}",
                timeout=300.0  # Longer timeout for sync mode
            )
            response.raise_for_status()
            result = response.json()
            
            summary = result['execution_summary']
            
            print(f"✅ Warmup completed!")
            print(f"📊 Results: {summary['successful_actions']}/{summary['total_actions']} successful")
            print(f"📢 Joined channels: {', '.join(summary['joined_channels'])}\n")
            
            print("📝 Execution details:")
            for res in summary['results']:
                status = "✓" if res['success'] else "✗"
                action = res['action']
                print(f"  {status} Step {res['step']}: {action['action']} - {action.get('reason', 'N/A')}")
            
            if summary['errors']:
                print(f"\n⚠️  {len(summary['errors'])} errors occurred:")
                for error in summary['errors']:
                    print(f"  - Step {error['step']}: {error['error']}")
            
            return result
            
        except httpx.HTTPStatusError as e:
            print(f"❌ HTTP Error: {e.response.status_code}")
            print(f"   {e.response.text}")
        except Exception as e:
            print(f"❌ Error: {str(e)}")


async def check_health(base_url: str = "http://localhost:8080"):
    """
    Check service health
    """
    print(f"🏥 Checking service health at {base_url}...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{base_url}/health", timeout=5.0)
            response.raise_for_status()
            health = response.json()
            
            print(f"✅ Service is healthy!")
            print(f"   Telegram client: {'✓' if health['telegram_client'] else '✗'}")
            print(f"   LLM agent: {'✓' if health['llm_agent'] else '✗'}")
            
            return health
            
        except Exception as e:
            print(f"❌ Service unavailable: {str(e)}")
            return None


async def main():
    """Main example runner"""
    
    # Configuration
    BASE_URL = "http://localhost:8080"
    SESSION_ID = "example_session_abc123"  # Replace with real session ID
    
    print("=" * 60)
    print("🔥 Heat Up Service - Example Usage")
    print("=" * 60)
    print()
    
    # 1. Check service health
    await check_health(BASE_URL)
    print()
    
    # 2. Choose mode
    print("Choose warmup mode:")
    print("  1. Async (fast, returns immediately)")
    print("  2. Sync (waits for completion)")
    
    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        choice = input("\nEnter choice (1 or 2): ").strip()
    
    print()
    
    if choice == "1":
        await warmup_session_async(SESSION_ID, BASE_URL)
    elif choice == "2":
        await warmup_session_sync(SESSION_ID, BASE_URL)
    else:
        print("Invalid choice!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user")

