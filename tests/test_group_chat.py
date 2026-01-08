"""
Group chat test - verifies complete flow of creating and using bot groups.

This script:
1. Creates a new private group with multiple bot accounts
2. Sends initial messages
3. Processes group activities
4. Verifies messages in database
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from datetime import datetime

from database import (
    init_database,
    get_accounts_eligible_for_dm,
    get_bot_group,
    get_group_members,
    get_group_messages,
    update_bot_group,
    count_active_bot_groups,
)
from group_engine import get_group_engine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def find_valid_accounts_for_group(min_count: int = 3):
    """Find accounts that can participate in a group"""
    eligible = get_accounts_eligible_for_dm()
    logger.info(f"Found {len(eligible)} eligible accounts")

    if len(eligible) < min_count:
        logger.warning(f"Need at least {min_count} accounts, found {len(eligible)}")
        return []

    return eligible[:min_count + 2]  # Return a few extra


async def test_group_creation():
    """Test creating a new group with bot accounts"""
    logger.info("=" * 80)
    logger.info("GROUP CREATION TEST")
    logger.info("=" * 80)

    init_database()
    engine = get_group_engine()

    # 1. Find accounts for the group
    logger.info("Finding accounts for group...")
    accounts = await find_valid_accounts_for_group(3)

    if len(accounts) < 3:
        logger.error(f"Not enough accounts for test (need 3, found {len(accounts)})")
        return None

    creator = accounts[0]
    members = [acc["session_id"] for acc in accounts[1:4]]

    logger.info(f"Creator: {creator['session_id'][:8]} ({creator.get('generated_name', 'Unknown')})")
    for i, m in enumerate(members):
        acc = next((a for a in accounts if a["session_id"] == m), {})
        logger.info(f"Member {i+1}: {m[:8]} ({acc.get('generated_name', 'Unknown')})")

    # 2. Create the group
    logger.info("\n--- STEP 1: Creating group ---")
    group = await engine.create_new_group(
        creator_session_id=creator["session_id"],
        group_type="friends",
        topic="Тестовый чат",
        initial_member_ids=members
    )

    if not group:
        logger.error("Failed to create group")
        return None

    group_id = group["id"]
    logger.info(f"Group created: ID={group_id}, title='{group.get('group_title')}'")
    logger.info(f"Telegram chat_id: {group.get('telegram_chat_id')}")
    logger.info(f"Invite link: {group.get('telegram_invite_link')}")

    # 3. Verify members
    logger.info("\n--- STEP 2: Verifying members ---")
    group_members = get_group_members(group_id)
    logger.info(f"Group has {len(group_members)} members:")
    for member in group_members:
        logger.info(f"  - {member.get('generated_name', 'Unknown')} ({member['role']})")

    return group_id


async def test_group_activity(group_id: int):
    """Test sending messages in a group"""
    logger.info("\n" + "=" * 80)
    logger.info("GROUP ACTIVITY TEST")
    logger.info("=" * 80)

    engine = get_group_engine()
    group = get_bot_group(group_id)

    if not group:
        logger.error(f"Group {group_id} not found")
        return False

    # 1. Force immediate activity by setting next_activity_after to past
    logger.info("--- STEP 1: Processing first activity ---")
    update_bot_group(group_id, next_activity_after=datetime.utcnow())

    # Process activities
    messages_sent = await engine.process_group_activities()
    logger.info(f"Messages sent: {messages_sent}")

    # 2. Get messages
    messages = get_group_messages(group_id)
    logger.info(f"Messages in group: {len(messages)}")

    if messages:
        for i, msg in enumerate(messages):
            logger.info(f"  [{i+1}] {msg.get('sender_name', 'Unknown')}: {msg['message_text'][:60]}...")

    # 3. Send another message
    logger.info("\n--- STEP 2: Processing second activity ---")
    update_bot_group(group_id, next_activity_after=datetime.utcnow())

    messages_sent = await engine.process_group_activities()
    logger.info(f"Messages sent: {messages_sent}")

    messages = get_group_messages(group_id)
    logger.info(f"Messages in group after second activity: {len(messages)}")

    return len(messages) >= 2


async def test_group_message_generation():
    """Test LLM generation for group messages (without sending)"""
    logger.info("\n" + "=" * 80)
    logger.info("GROUP MESSAGE GENERATION TEST")
    logger.info("=" * 80)

    from conversation_agent import get_conversation_agent

    agent = get_conversation_agent()

    # Mock personas
    sender_persona = {
        "generated_name": "Алексей",
        "age": 28,
        "occupation": "программист",
        "personality_traits": ["дружелюбный", "любознательный"],
        "communication_style": "неформальный",
        "interests": ["технологии", "игры", "кино"]
    }

    other_personas = [
        {
            "generated_name": "Марина",
            "age": 25,
            "occupation": "дизайнер",
            "interests": ["искусство", "путешествия", "кино"]
        },
        {
            "generated_name": "Дмитрий",
            "age": 30,
            "occupation": "маркетолог",
            "interests": ["бизнес", "спорт", "технологии"]
        }
    ]

    # Test 1: First message (starter)
    logger.info("--- TEST 1: Group starter message ---")
    starter = await agent.generate_group_message(
        my_persona=sender_persona,
        group_members=other_personas,
        group_topic="Кино и сериалы",
        group_type="thematic",
        recent_messages=[]
    )

    if starter:
        logger.info(f"Generated starter: {starter}")
        logger.info("PASSED")
    else:
        logger.warning("Failed to generate starter")

    # Test 2: Response message
    logger.info("\n--- TEST 2: Group response message ---")

    recent_messages = [
        {"sender_name": "Марина", "message_text": "Смотрели новый сезон?"},
        {"sender_name": "Дмитрий", "message_text": "Да, классный! Особенно последняя серия"}
    ]

    response = await agent.generate_group_message(
        my_persona=sender_persona,
        group_members=other_personas,
        group_topic="Кино и сериалы",
        group_type="thematic",
        recent_messages=recent_messages
    )

    if response:
        logger.info(f"Generated response: {response}")
        logger.info("PASSED")
    else:
        logger.warning("Failed to generate response")

    return starter is not None and response is not None


async def main():
    """Run all tests"""
    try:
        results = []

        # Test 1: Message generation (doesn't require Telegram)
        results.append(('Group Message Generation', await test_group_message_generation()))

        # Test 2: Group creation (requires Telegram)
        group_id = await test_group_creation()
        results.append(('Group Creation', group_id is not None))

        # Test 3: Group activity (requires created group)
        if group_id:
            results.append(('Group Activity', await test_group_activity(group_id)))

            # Cleanup: archive the test group
            update_bot_group(group_id, status='archived')
            logger.info(f"\nTest group {group_id} archived")
        else:
            results.append(('Group Activity', False))

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("FINAL TEST SUMMARY")
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

    except Exception as e:
        logger.error(f"Test failed with exception: {e}", exc_info=True)
        return False


if __name__ == '__main__':
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
