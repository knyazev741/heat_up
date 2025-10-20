#!/usr/bin/env python3
"""
Test sponsored messages functionality
Usage: python tests/test_sponsored_ads.py <session_id> <channel_username>
Example: python tests/test_sponsored_ads.py 27031 @SecretAdTestChannel
"""

import sys
import asyncio
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram_client import TelegramAPIClient
from config import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_sponsored_messages(session_id: str, channel_username: str):
    """Test sponsored messages retrieval"""
    
    logger.info("=" * 80)
    logger.info(f"Testing Sponsored Messages")
    logger.info(f"Session: {session_id}")
    logger.info(f"Channel: {channel_username}")
    logger.info("=" * 80)
    
    client = TelegramAPIClient()
    
    try:
        # Step 1: Get session info (check premium status)
        logger.info("\n📱 Step 1: Checking session premium status...")
        session_info = await client.get_session_info(session_id)
        
        if session_info.get("error"):
            logger.error(f"❌ Failed to get session info: {session_info.get('error')}")
            return False
        
        is_premium = session_info.get("is_premium", False)
        logger.info(f"✅ Session {session_id} premium status: {is_premium}")
        
        if is_premium:
            logger.warning("⚠️  Session is premium - sponsored messages may not be available")
        
        # Step 2: Get sponsored messages
        logger.info(f"\n🎯 Step 2: Fetching sponsored messages for {channel_username}...")
        sponsored_result = await client.get_sponsored_messages(
            session_id,
            channel_username
        )
        
        if sponsored_result.get("error"):
            logger.error(f"❌ Failed to get sponsored messages: {sponsored_result.get('error')}")
            logger.info(f"Full response: {sponsored_result}")
            return False
        
        if not sponsored_result.get("success"):
            logger.error(f"❌ Request failed: {sponsored_result}")
            return False
        
        # Step 3: Parse and display results
        logger.info("\n✅ Successfully retrieved sponsored messages!")
        
        result_data = sponsored_result.get("result", {})
        messages = result_data.get("messages", [])
        posts_between = result_data.get("posts_between")
        
        logger.info(f"\n📊 Results:")
        logger.info(f"  Posts between ads: {posts_between}")
        logger.info(f"  Number of ads: {len(messages)}")
        
        if messages and len(messages) > 0:
            logger.info(f"\n📢 Found {len(messages)} sponsored message(s):")
            
            for idx, ad in enumerate(messages, 1):
                logger.info(f"\n  📣 Ad #{idx}:")
                logger.info(f"    Title: {ad.get('title', '')}")
                
                message = ad.get('message', '')
                if len(message) > 100:
                    logger.info(f"    Message: {message[:100]}...")
                else:
                    logger.info(f"    Message: {message}")
                
                logger.info(f"    URL: {ad.get('url', '')}")
                logger.info(f"    Button: {ad.get('button_text', '')}")
                logger.info(f"    Recommended: {ad.get('recommended', False)}")
                logger.info(f"    Random ID: {ad.get('random_id', 'N/A')}")
                
                # Test viewing the ad
                random_id = ad.get('random_id')
                if random_id:
                    logger.info(f"\n  👁️  Step 3.{idx}: Marking ad #{idx} as viewed...")
                    try:
                        view_result = await client.view_sponsored_message(
                            session_id,
                            random_id
                        )
                        
                        if view_result.get("success"):
                            logger.info(f"    ✅ Successfully marked ad #{idx} as viewed")
                        else:
                            logger.warning(f"    ⚠️  Failed to mark as viewed: {view_result.get('error')}")
                    except Exception as e:
                        logger.error(f"    ❌ Exception marking ad as viewed: {e}")
        else:
            logger.info("\n📭 No sponsored messages available for this channel")
            logger.info("   This could mean:")
            logger.info("   - Channel doesn't have ads")
            logger.info("   - Account is premium")
            logger.info("   - Ads expired or not available in region")
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ TEST COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Exception during test: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await client.close()


async def test_join_with_ads(session_id: str, channel_username: str):
    """Test join_channel with sponsored messages"""
    
    logger.info("\n" + "=" * 80)
    logger.info("Testing Join Channel with Sponsored Messages")
    logger.info("=" * 80)
    
    from executor import ActionExecutor
    
    client = TelegramAPIClient()
    executor = ActionExecutor(client)
    
    try:
        action = {
            "action": "join_channel",
            "channel_username": channel_username
        }
        
        logger.info(f"\n🚀 Executing join_channel action for {channel_username}...")
        result = await executor._join_channel(session_id, action)
        
        logger.info(f"\n📊 Result:")
        logger.info(f"  Success: {not result.get('error')}")
        logger.info(f"  Is Premium: {result.get('is_premium', 'N/A')}")
        logger.info(f"  Sponsored Ads Count: {result.get('sponsored_ads_count', 0)}")
        
        if result.get('sponsored_ads'):
            logger.info(f"\n📢 Sponsored Ads Retrieved:")
            for idx, ad in enumerate(result['sponsored_ads'], 1):
                logger.info(f"  Ad #{idx}: {ad.get('title', 'No title')}")
        
        if result.get('error'):
            logger.error(f"❌ Error: {result['error']}")
            return False
        
        logger.info("\n✅ Join with ads test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"\n❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await client.close()


async def main():
    if len(sys.argv) < 3:
        print("Usage: python tests/test_sponsored_ads.py <session_id> <channel_username>")
        print("Example: python tests/test_sponsored_ads.py 27031 @SecretAdTestChannel")
        sys.exit(1)
    
    session_id = sys.argv[1]
    channel_username = sys.argv[2]
    
    # Ensure @ prefix
    if not channel_username.startswith('@'):
        channel_username = f'@{channel_username}'
    
    # Test 1: Direct API call
    success1 = await test_sponsored_messages(session_id, channel_username)
    
    # Test 2: Via join_channel action
    success2 = await test_join_with_ads(session_id, channel_username)
    
    if success1 and success2:
        logger.info("\n🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        logger.error("\n❌ SOME TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

