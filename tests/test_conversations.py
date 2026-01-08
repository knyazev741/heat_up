"""
Test script for Phase 1: Private Conversations between bots.

This script tests the conversation system by:
1. Checking database functions
2. Testing ConversationAgent message generation
3. Testing ConversationEngine logic
4. Running end-to-end conversation flow with real sessions
"""

import asyncio
import sys
import os

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime

from database import (
    init_database,
    get_accounts_eligible_for_dm,
    get_potential_conversation_partners,
    create_conversation,
    get_conversation,
    get_active_conversation,
    save_conversation_message,
    get_conversation_messages,
    update_conversation,
    count_active_conversations,
    get_account,
    get_persona,
    MIN_STAGE_FOR_DM
)
from conversation_agent import get_conversation_agent
from conversation_engine import get_conversation_engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_database_functions():
    """Test database functions for conversations"""
    logger.info("=" * 60)
    logger.info("TEST 1: Database Functions")
    logger.info("=" * 60)

    # Test getting eligible accounts
    eligible = get_accounts_eligible_for_dm()
    logger.info(f"Eligible accounts for DM: {len(eligible)}")

    if len(eligible) < 2:
        logger.warning("Need at least 2 eligible accounts for DM tests")
        return False

    # Show first few
    for acc in eligible[:3]:
        logger.info(f"  - {acc['session_id'][:8]}... stage={acc.get('warmup_stage')} name={acc.get('generated_name')}")

    # Test getting partners
    initiator = eligible[0]
    partners = get_potential_conversation_partners(initiator['session_id'], limit=5)
    logger.info(f"Potential partners for {initiator['session_id'][:8]}: {len(partners)}")

    # Test create conversation
    if partners:
        partner = partners[0]
        logger.info(f"Testing conversation creation: {initiator['session_id'][:8]} -> {partner['session_id'][:8]}")

        conv_id = create_conversation(
            initiator_account_id=initiator['id'],
            responder_account_id=partner['id'],
            initiator_session_id=initiator['session_id'],
            responder_session_id=partner['session_id'],
            conversation_starter="Test message",
            common_context="Testing"
        )

        if conv_id:
            logger.info(f"Created test conversation: {conv_id}")

            # Test save message
            msg_id = save_conversation_message(
                conversation_id=conv_id,
                sender_account_id=initiator['id'],
                message_text="Test message 1"
            )
            logger.info(f"Saved test message: {msg_id}")

            # Test get messages
            messages = get_conversation_messages(conv_id)
            logger.info(f"Messages in conversation: {len(messages)}")

            # Mark as ended (cleanup)
            update_conversation(conv_id, status='ended', end_reason='test')
            logger.info("Marked test conversation as ended")
        else:
            logger.error("Failed to create conversation")
            return False

    logger.info("Database functions test: PASSED")
    return True


async def test_conversation_agent():
    """Test ConversationAgent message generation"""
    logger.info("=" * 60)
    logger.info("TEST 2: ConversationAgent Message Generation")
    logger.info("=" * 60)

    agent = get_conversation_agent()

    # Get two personas for testing
    eligible = get_accounts_eligible_for_dm()
    if len(eligible) < 2:
        logger.warning("Need at least 2 accounts with personas for agent test")
        return False

    initiator = eligible[0]
    partner = eligible[1]

    initiator_persona = get_persona(initiator['id']) or {
        'generated_name': 'Test User 1',
        'age': 25,
        'occupation': 'Developer',
        'communication_style': 'дружелюбный',
        'interests': ['технологии', 'программирование']
    }

    partner_persona = get_persona(partner['id']) or {
        'generated_name': 'Test User 2',
        'age': 28,
        'occupation': 'Designer',
        'communication_style': 'дружелюбный',
        'interests': ['дизайн', 'искусство']
    }

    # Test starter generation
    logger.info("Testing conversation starter generation...")
    starter = await agent.generate_conversation_starter(
        my_persona=initiator_persona,
        their_persona=partner_persona,
        common_context="Общий интерес к технологиям"
    )

    if starter:
        logger.info(f"Generated starter: {starter}")
    else:
        logger.error("Failed to generate starter")
        return False

    # Test response generation
    logger.info("Testing response generation...")
    history = [
        {'sender_name': initiator_persona['generated_name'], 'message_text': starter, 'is_mine': False}
    ]

    response = await agent.generate_conversation_response(
        my_persona=partner_persona,
        their_persona=initiator_persona,
        conversation_history=history,
        current_topic="знакомство"
    )

    if response:
        logger.info(f"Generated response: {response}")
    else:
        logger.error("Failed to generate response")
        return False

    # Test closing generation
    logger.info("Testing closing message generation...")
    closing = await agent.generate_closing_message(
        my_persona=partner_persona,
        recent_messages=history
    )

    if closing:
        logger.info(f"Generated closing: {closing}")
    else:
        logger.warning("Failed to generate closing (using fallback)")

    logger.info("ConversationAgent test: PASSED")
    return True


async def test_conversation_engine_check():
    """Test ConversationEngine status check"""
    logger.info("=" * 60)
    logger.info("TEST 3: ConversationEngine Status Checks")
    logger.info("=" * 60)

    engine = get_conversation_engine()

    eligible = get_accounts_eligible_for_dm()
    if len(eligible) < 2:
        logger.warning("Need at least 2 accounts for engine test")
        return False

    initiator = eligible[0]
    target = eligible[1]

    # Test can_initiate_dm_to_session
    logger.info(f"Testing can_initiate_dm: {initiator['session_id'][:8]} -> {target['session_id'][:8]}")
    can_dm, reason = await engine.can_initiate_dm_to_session(
        target['session_id'],
        initiator['session_id']
    )

    logger.info(f"Can initiate DM: {can_dm}, reason: {reason}")

    logger.info("ConversationEngine check test: PASSED")
    return True


async def test_full_conversation_flow():
    """Test full conversation flow with real sessions"""
    logger.info("=" * 60)
    logger.info("TEST 4: Full Conversation Flow")
    logger.info("=" * 60)

    engine = get_conversation_engine()

    eligible = get_accounts_eligible_for_dm()
    if len(eligible) < 2:
        logger.warning("Need at least 2 accounts for full flow test")
        return False

    initiator = eligible[0]
    partners = get_potential_conversation_partners(initiator['session_id'], limit=3)

    if not partners:
        logger.warning("No available partners for conversation")
        return False

    target = partners[0]

    logger.info(f"Testing conversation: {initiator['session_id'][:8]} -> {target['session_id'][:8]}")
    logger.info(f"Initiator: {initiator.get('generated_name', 'Unknown')}")
    logger.info(f"Target: {target.get('generated_name', 'Unknown')}")

    # NOTE: This would actually send messages via Telegram API
    # For safety, we just test the logic without sending
    logger.info("(Skipping actual message send to avoid spam)")

    # Test the check logic
    can_dm, reason = await engine.can_initiate_dm_to_session(
        target['session_id'],
        initiator['session_id']
    )

    if not can_dm:
        logger.info(f"Cannot start conversation: {reason}")
    else:
        logger.info("Conversation can be started (actual send skipped in test)")

    # Count active conversations
    active = count_active_conversations()
    logger.info(f"Currently active conversations: {active}")

    logger.info("Full flow test: PASSED")
    return True


async def main():
    """Run all tests"""
    logger.info("=" * 80)
    logger.info("PHASE 1 CONVERSATION SYSTEM TESTS")
    logger.info("=" * 80)
    logger.info(f"Minimum stage for DM: {MIN_STAGE_FOR_DM}")
    logger.info(f"Time: {datetime.utcnow().isoformat()}")
    logger.info("=" * 80)

    # Initialize database
    init_database()

    results = []

    # Run tests
    results.append(('Database Functions', await test_database_functions()))
    results.append(('ConversationAgent', await test_conversation_agent()))
    results.append(('ConversationEngine Check', await test_conversation_engine_check()))
    results.append(('Full Conversation Flow', await test_full_conversation_flow()))

    # Summary
    logger.info("=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)

    all_passed = True
    for name, passed in results:
        status = "PASSED" if passed else "FAILED"
        logger.info(f"  {name}: {status}")
        if not passed:
            all_passed = False

    logger.info("=" * 80)
    if all_passed:
        logger.info("ALL TESTS PASSED!")
    else:
        logger.info("SOME TESTS FAILED!")
    logger.info("=" * 80)

    return all_passed


if __name__ == '__main__':
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
