#!/usr/bin/env python3
"""
Test Admin API Client

This script tests the Admin API client functionality
"""

import asyncio
import sys
import logging
from admin_api_client import AdminAPIClient

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_admin_api():
    """Test Admin API client"""
    
    client = AdminAPIClient()
    
    try:
        logger.info("=" * 100)
        logger.info("Testing Admin API Client")
        logger.info("=" * 100)
        
        # Test 1: Get frozen sessions
        logger.info("\n📊 Test 1: Get frozen sessions (first 5)")
        result = await client.get_sessions(frozen=True, limit=5)
        logger.info(f"✅ Total frozen sessions: {result.get('total', 0)}")
        logger.info(f"✅ Fetched {len(result.get('items', []))} sessions")
        
        if result.get('items'):
            first_session = result['items'][0]
            logger.info(f"✅ Sample session ID: {first_session.get('id')}, Phone: {first_session.get('phone_number')}, Frozen: {first_session.get('frozen')}")
        
        # Test 2: Get deleted sessions
        logger.info("\n📊 Test 2: Get deleted sessions count")
        result = await client.get_sessions(deleted=True, limit=1)
        logger.info(f"✅ Total deleted sessions: {result.get('total', 0)}")
        
        # Test 3: Get banned forever sessions
        logger.info("\n📊 Test 3: Get banned forever sessions count")
        result = await client.get_sessions(spamblock=True, limit=100)
        forever_banned = [
            s for s in result.get('items', [])
            if s.get('spamblock') and not s.get('unban_date')
        ]
        logger.info(f"✅ Banned forever sessions: {len(forever_banned)}")
        
        # Test 4: Get a specific session by ID (if we have one)
        if result.get('items'):
            test_id = result['items'][0].get('id')
            logger.info(f"\n📊 Test 4: Get session by ID ({test_id})")
            session = await client.get_session_by_id(test_id)
            if session:
                logger.info(f"✅ Retrieved session: ID={session.get('id')}, Phone={session.get('phone_number')}")
            else:
                logger.warning(f"⚠️ Session {test_id} not found")
        
        # Test 5: Get session by phone
        logger.info("\n📊 Test 5: Get session by phone (test with a known phone if available)")
        # This will likely return 404, that's OK
        session = await client.get_session_by_phone("79999999999")
        if session:
            logger.info(f"✅ Retrieved session by phone: {session.get('id')}")
        else:
            logger.info("ℹ️ Session not found (expected for test phone)")
        
        # Test 6: Summary of problematic sessions
        logger.info("\n" + "=" * 100)
        logger.info("📊 SUMMARY OF PROBLEMATIC SESSIONS")
        logger.info("=" * 100)
        
        frozen_result = await client.get_sessions(frozen=True, limit=1)
        deleted_result = await client.get_sessions(deleted=True, limit=1)
        banned_result = await client.get_sessions(spamblock=True, limit=100)
        forever_banned_count = sum(
            1 for s in banned_result.get('items', [])
            if s.get('spamblock') and not s.get('unban_date')
        )
        
        logger.info(f"🧊 Frozen sessions:         {frozen_result.get('total', 0)}")
        logger.info(f"❌ Deleted sessions:        {deleted_result.get('total', 0)}")
        logger.info(f"🚫 Banned forever sessions: {forever_banned_count}")
        logger.info(f"📊 Total to exclude:        {frozen_result.get('total', 0) + deleted_result.get('total', 0) + forever_banned_count}")
        logger.info("=" * 100)
        
        logger.info("\n✅ All tests completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error during testing: {e}", exc_info=True)
        return False
    finally:
        await client.close()
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_admin_api())
    sys.exit(0 if success else 1)

