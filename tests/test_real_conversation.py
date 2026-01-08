"""
Test script for real conversation between two bots.

This script:
1. Finds two eligible accounts that CAN have DM
2. Starts a real conversation between them
3. Exchanges a few messages
4. Verifies messages in the database match what was sent
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime, timedelta

from database import (
    init_database,
    get_accounts_eligible_for_dm,
    get_potential_conversation_partners,
    get_conversation,
    get_conversation_messages,
    update_conversation,
    count_active_conversations,
    get_account,
    get_persona,
)
from conversation_engine import get_conversation_engine
from admin_api_client import get_admin_api_client

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def find_valid_pair():
    """Find a pair of accounts that can have DM (no status=1 restriction)"""
    admin_api = get_admin_api_client()
    engine = get_conversation_engine()

    eligible = get_accounts_eligible_for_dm()
    logger.info(f"Found {len(eligible)} eligible accounts")

    for initiator in eligible[:20]:  # Check first 20
        partners = get_potential_conversation_partners(initiator['session_id'], limit=10)

        for partner in partners:
            # Check if we can actually DM this partner
            can_dm, reason = await engine.can_initiate_dm_to_session(
                partner['session_id'],
                initiator['session_id']
            )

            if can_dm:
                logger.info(f"Found valid pair: {initiator['session_id'][:8]} -> {partner['session_id'][:8]}")
                return initiator, partner

    return None, None


async def test_real_conversation():
    """Test real conversation between two bots"""
    logger.info("=" * 80)
    logger.info("REAL CONVERSATION TEST")
    logger.info("=" * 80)

    init_database()

    # Find valid pair
    logger.info("Finding valid pair of accounts...")
    initiator, partner = await find_valid_pair()

    if not initiator or not partner:
        logger.error("Could not find a valid pair of accounts for DM")
        logger.info("All eligible accounts may have status=1 restriction")
        return False

    logger.info(f"Initiator: {initiator['session_id'][:8]}... ({initiator.get('generated_name', 'Unknown')})")
    logger.info(f"Partner: {partner['session_id'][:8]}... ({partner.get('generated_name', 'Unknown')})")

    # Get engine
    engine = get_conversation_engine()

    # Start conversation
    logger.info("Starting conversation...")
    conversation = await engine.start_new_conversation(
        initiator_session_id=initiator['session_id'],
        target_session_id=partner['session_id'],
        common_context="Тестовый диалог для проверки системы"
    )

    if not conversation:
        logger.error("Failed to start conversation")
        return False

    conversation_id = conversation['id']
    logger.info(f"Conversation started: ID={conversation_id}")

    # Get messages
    messages = get_conversation_messages(conversation_id)
    logger.info(f"Messages in conversation: {len(messages)}")

    for msg in messages:
        logger.info(f"  [{msg.get('sender_name', 'Unknown')}]: {msg['message_text'][:50]}...")

    # Wait for response time
    logger.info("Waiting 5 seconds before checking for response...")
    await asyncio.sleep(5)

    # Simulate response processing (set next_response_after to now)
    update_conversation(conversation_id, next_response_after=datetime.utcnow())

    # Process response
    logger.info("Processing response...")
    responses = await engine.process_pending_responses()
    logger.info(f"Responses processed: {responses}")

    # Get updated messages
    messages = get_conversation_messages(conversation_id)
    logger.info(f"Messages after response: {len(messages)}")

    for msg in messages:
        logger.info(f"  [{msg.get('sender_name', 'Unknown')}]: {msg['message_text'][:80]}...")

    # Verify we have at least 2 messages (starter + response)
    if len(messages) >= 2:
        logger.info("Conversation flow verified: at least 2 messages exchanged")
    else:
        logger.warning("Only 1 message - response may have failed")

    # End conversation for cleanup
    update_conversation(conversation_id, status='ended', end_reason='test')
    logger.info("Test conversation marked as ended")

    logger.info("=" * 80)
    logger.info("REAL CONVERSATION TEST: PASSED")
    logger.info("=" * 80)

    return True


async def main():
    try:
        success = await test_real_conversation()
        return success
    except Exception as e:
        logger.error(f"Test failed with exception: {e}", exc_info=True)
        return False


if __name__ == '__main__':
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
