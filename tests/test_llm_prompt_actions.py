"""
Test LLM prompt with synthetic data to verify action generation.

This test:
1. Creates synthetic data matching real warmup conditions
2. Tests reply_to_dm action generation with pending DMs
3. Tests group chat actions (reply_in_chat)
4. Verifies LLM produces expected action types

Run: python tests/test_llm_prompt_actions.py
"""

import asyncio
import sys
import os
import json
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_agent import ActionPlannerAgent
from config import settings

# LLM Configuration
LLM_CONFIG = {
    "api_key": settings.deepseek_api_key,
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-chat"
}

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Synthetic data matching real warmup conditions
SYNTHETIC_ACCOUNT = {
    "id": 999,
    "session_id": "99999",
    "warmup_stage": 5,  # Stage 5+ allows reactions, bots, reply_to_dm
    "phone_number": "+79001234567",
    "is_active": True,
    "account_type": "warmup"
}

SYNTHETIC_PERSONA = {
    "generated_name": "Мария Соколова",
    "age": 28,
    "occupation": "дизайнер интерьеров",
    "city": "Казань",
    "country": "Россия",
    "interests": ["дизайн", "архитектура", "путешествия", "кулинария", "йога"],
    "personality_traits": ["креативная", "общительная", "внимательная к деталям"],
    "communication_style": "дружелюбный и профессиональный",
    "activity_level": "средний",
    "full_description": "Мария - талантливый дизайнер интерьеров из Казани. Любит путешествовать и находить вдохновение в архитектуре разных стран.",
    "background_story": "Закончила архитектурный факультет, работает в студии дизайна уже 5 лет."
}

SYNTHETIC_PENDING_DMS = [
    {
        "conversation_id": 42,
        "sender_name": "Алексей Петров",
        "last_message_text": "Привет! Видела твои работы по дизайну, очень понравилось! Можешь рассказать подробнее о своём стиле?",
        "peer_session_id": "12345"
    },
    {
        "conversation_id": 43,
        "sender_name": "Ирина Волкова",
        "last_message_text": "Привет, Мария! Как дела? Давно не общались. Ты всё ещё в Казани?",
        "peer_session_id": "12346"
    }
]

SYNTHETIC_RELEVANT_CHATS = [
    {"chat_username": "@design_kazan", "chat_title": "Дизайн интерьеров Казань", "chat_type": "group", "is_joined": True, "relevance_score": 0.95, "relevance_reason": "Профессиональное сообщество дизайнеров"},
    {"chat_username": "@travel_russia", "chat_title": "Путешествия по России", "chat_type": "channel", "is_joined": True, "relevance_score": 0.85, "relevance_reason": "Интерес к путешествиям"},
    {"chat_username": "@yoga_kazan", "chat_title": "Йога Казань", "chat_type": "group", "is_joined": False, "relevance_score": 0.80, "relevance_reason": "Интерес к йоге"},
    {"chat_username": "@architecture_news", "chat_title": "Новости архитектуры", "chat_type": "channel", "is_joined": True, "relevance_score": 0.75, "relevance_reason": "Профессиональный интерес"},
    {"chat_username": "@cooking_recipes", "chat_title": "Рецепты и кулинария", "chat_type": "channel", "is_joined": False, "relevance_score": 0.70, "relevance_reason": "Интерес к кулинарии"},
]


def build_test_prompt_with_pending_dms() -> str:
    """Build prompt with synthetic pending DMs to test reply_to_dm generation."""

    persona = SYNTHETIC_PERSONA
    account = SYNTHETIC_ACCOUNT
    pending_dms = SYNTHETIC_PENDING_DMS
    chats = SYNTHETIC_RELEVANT_CHATS

    # Build pending DMs context (same as in llm_agent.py)
    dm_lines = []
    for dm in pending_dms:
        sender_name = dm.get('sender_name', 'Неизвестный')
        last_msg = dm.get('last_message_text', '')[:100]
        conv_id = dm.get('conversation_id')
        dm_lines.append(f"- От {sender_name} (conversation_id={conv_id}): \"{last_msg}...\"")

    pending_dms_context = f"""
📬 НЕПРОЧИТАННЫЕ СООБЩЕНИЯ В ЛС:
У тебя есть непрочитанные сообщения от других пользователей! Ты можешь ответить на них, если хочешь.

{chr(10).join(dm_lines)}

Чтобы ответить, используй действие reply_to_dm с conversation_id.
"""

    # Build channels list
    channels_list = "\n".join([
        f"- {ch['chat_username']}: {ch.get('chat_title', 'Unknown')} "
        f"[{(ch.get('chat_type') or 'unknown').upper()}] "
        f"{'[ВСТУПИЛ ✅]' if ch.get('is_joined') else '[НОВЫЙ]'} "
        f"(релевантность: {ch.get('relevance_score', 0):.1f}) - {ch.get('relevance_reason', '')[:80]}"
        for ch in chats
    ])

    prompt = f"""ТЫ - это реальный пользователь Telegram со следующей личностью:

Имя: {persona['generated_name']}
Возраст: {persona['age']} лет
Профессия: {persona['occupation']}
Город: {persona['city']}, {persona['country']}
Интересы: {', '.join(persona['interests'])}
Характер: {', '.join(persona['personality_traits'])}
Стиль общения: {persona['communication_style']}
Уровень активности: {persona['activity_level']}

О тебе:
{persona['full_description']}

📅 ТЕКУЩАЯ СТАДИЯ ПРОГРЕВА: День {account['warmup_stage']}

ЛИМИТЫ ДЛЯ ЭТОЙ СТАДИИ:
- Максимум действий: 15
- Максимум вступлений в новые чаты: 3
- Максимум отправленных сообщений: 2

{pending_dms_context}

📋 ДОСТУПНЫЕ ЧАТЫ/КАНАЛЫ (подобраны СПЕЦИАЛЬНО для ТВОИХ интересов):
{channels_list}

ДОСТУПНЫЕ ТИПЫ ДЕЙСТВИЙ:

1. join_channel (join_chat):
   {{"action": "join_channel", "channel_username": "@example", "reason": "Интересная тематика"}}

2. read_messages:
   {{"action": "read_messages", "channel_username": "@example", "duration_seconds": 15, "reason": "Читаю контент"}}

3. idle:
   {{"action": "idle", "duration_seconds": 7, "reason": "Короткая пауза"}}

4. view_profile:
   {{"action": "view_profile", "channel_username": "@example", "duration_seconds": 5, "reason": "Изучаю чат/канал"}}

5. "react_to_message" - Поставить реакцию на сообщение
   - Params: channel_username (или chat_username)

6. "reply_to_dm" - Ответить на личное сообщение
   - Params: conversation_id, message (текст ответа)
   - Используй если есть непрочитанные сообщения в ЛС (см. выше)
   - Пример: {{"action": "reply_to_dm", "conversation_id": 123, "message": "Привет! Да, интересная тема..."}}

7. "reply_in_chat" - Ответить на сообщение в группе
   - Params: chat_username, reply_text

⚠️ ВАЖНО: У тебя есть непрочитанные сообщения в ЛС! Обрати на них внимание и ответь если хочешь.

Стадия: {account['warmup_stage']}
Формат ответа - ТОЛЬКО JSON массив, без текста!"""

    return prompt


def build_test_prompt_for_group_reply() -> str:
    """Build prompt to test reply_in_chat for group messages."""

    persona = SYNTHETIC_PERSONA
    account = SYNTHETIC_ACCOUNT.copy()
    account["warmup_stage"] = 10  # Stage 10+ for reply_in_chat
    chats = SYNTHETIC_RELEVANT_CHATS

    channels_list = "\n".join([
        f"- {ch['chat_username']}: {ch.get('chat_title', 'Unknown')} "
        f"[{(ch.get('chat_type') or 'unknown').upper()}] "
        f"{'[ВСТУПИЛ ✅]' if ch.get('is_joined') else '[НОВЫЙ]'} "
        f"(релевантность: {ch.get('relevance_score', 0):.1f})"
        for ch in chats
    ])

    # Simulate recent group messages that could trigger reply
    group_context = """
📢 ПОСЛЕДНИЕ СООБЩЕНИЯ В ГРУППАХ, ГДЕ ТЫ УЧАСТВУЕШЬ:

@design_kazan (Дизайн интерьеров Казань):
- Анна: "Кто-нибудь работал с натуральным камнем в интерьере? Ищу советы"
- Дмитрий: "Присоединяюсь к вопросу, тоже интересно"

Если хочешь ответить на сообщение в группе, используй reply_in_chat.
"""

    prompt = f"""ТЫ - это реальный пользователь Telegram со следующей личностью:

Имя: {persona['generated_name']}
Возраст: {persona['age']} лет
Профессия: {persona['occupation']}
Город: {persona['city']}, {persona['country']}
Интересы: {', '.join(persona['interests'])}

📅 ТЕКУЩАЯ СТАДИЯ ПРОГРЕВА: День {account['warmup_stage']}

ЛИМИТЫ ДЛЯ ЭТОЙ СТАДИИ:
- Максимум действий: 20
- Максимум вступлений в новые чаты: 5
- Максимум отправленных сообщений: 5

{group_context}

📋 ДОСТУПНЫЕ ЧАТЫ/КАНАЛЫ:
{channels_list}

ДОСТУПНЫЕ ТИПЫ ДЕЙСТВИЙ:

1. read_messages:
   {{"action": "read_messages", "channel_username": "@example", "duration_seconds": 15}}

2. idle:
   {{"action": "idle", "duration_seconds": 7, "reason": "Пауза"}}

3. "react_to_message" - Поставить реакцию
   - Params: channel_username

4. "reply_in_chat" - Ответить на сообщение в группе
   - Params: chat_username, reply_text
   - Пример: {{"action": "reply_in_chat", "chat_username": "@design_kazan", "reply_text": "Привет! Да, работала с камнем..."}}

⚠️ ВАЖНО: Ты профессиональный дизайнер. В группе @design_kazan спрашивают про натуральный камень - это твоя тема! Можешь помочь советом.

Стадия: {account['warmup_stage']}
Формат ответа - ТОЛЬКО JSON массив, без текста!"""

    return prompt


async def test_reply_to_dm_generation():
    """Test that LLM generates reply_to_dm action when pending DMs exist."""
    logger.info("=" * 80)
    logger.info("TEST 1: reply_to_dm action generation")
    logger.info("=" * 80)

    prompt = build_test_prompt_with_pending_dms()
    logger.info(f"Prompt length: {len(prompt)} chars")
    logger.info(f"Pending DMs in prompt: {len(SYNTHETIC_PENDING_DMS)}")

    # Use DeepSeek directly
    import httpx

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{LLM_CONFIG['base_url']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {LLM_CONFIG['api_key']}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": LLM_CONFIG["model"],
                    "messages": [
                        {"role": "system", "content": "Ты генератор действий для Telegram. Отвечай ТОЛЬКО JSON массивом."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 2000
                }
            )

            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # Parse JSON
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            actions = json.loads(content)

            logger.info(f"\n📋 Generated {len(actions)} actions:")

            has_reply_to_dm = False
            for i, action in enumerate(actions, 1):
                action_type = action.get("action", "unknown")
                logger.info(f"  {i}. {action_type}")
                if action_type == "reply_to_dm":
                    has_reply_to_dm = True
                    logger.info(f"     ✅ FOUND reply_to_dm!")
                    logger.info(f"     conversation_id: {action.get('conversation_id')}")
                    logger.info(f"     message: {action.get('message', '')[:50]}...")

            if has_reply_to_dm:
                logger.info("\n✅ TEST PASSED: LLM generated reply_to_dm action")
                return True
            else:
                logger.warning("\n⚠️ TEST WARNING: LLM did NOT generate reply_to_dm action")
                logger.info("This may be normal - LLM has freedom to choose actions")
                return False

    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        return False


async def test_reply_in_chat_generation():
    """Test that LLM generates reply_in_chat action for group messages."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: reply_in_chat action generation (group replies)")
    logger.info("=" * 80)

    prompt = build_test_prompt_for_group_reply()
    logger.info(f"Prompt length: {len(prompt)} chars")

    import httpx

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{LLM_CONFIG['base_url']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {LLM_CONFIG['api_key']}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": LLM_CONFIG["model"],
                    "messages": [
                        {"role": "system", "content": "Ты генератор действий для Telegram. Отвечай ТОЛЬКО JSON массивом."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 2000
                }
            )

            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # Parse JSON
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            actions = json.loads(content)

            logger.info(f"\n📋 Generated {len(actions)} actions:")

            has_reply_in_chat = False
            for i, action in enumerate(actions, 1):
                action_type = action.get("action", "unknown")
                logger.info(f"  {i}. {action_type}")
                if action_type == "reply_in_chat":
                    has_reply_in_chat = True
                    logger.info(f"     ✅ FOUND reply_in_chat!")
                    logger.info(f"     chat_username: {action.get('chat_username')}")
                    logger.info(f"     reply_text: {action.get('reply_text', '')[:50]}...")

            if has_reply_in_chat:
                logger.info("\n✅ TEST PASSED: LLM generated reply_in_chat action")
                return True
            else:
                logger.warning("\n⚠️ TEST WARNING: LLM did NOT generate reply_in_chat action")
                return False

    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        return False


async def main():
    logger.info("=" * 80)
    logger.info("LLM PROMPT ACTION GENERATION TESTS")
    logger.info("Testing with synthetic data matching real warmup conditions")
    logger.info("=" * 80)

    # Run tests multiple times to account for LLM randomness
    dm_successes = 0
    chat_successes = 0
    runs = 3

    for run in range(runs):
        logger.info(f"\n--- Run {run + 1}/{runs} ---")

        if await test_reply_to_dm_generation():
            dm_successes += 1

        if await test_reply_in_chat_generation():
            chat_successes += 1

    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"reply_to_dm generation: {dm_successes}/{runs} successful")
    logger.info(f"reply_in_chat generation: {chat_successes}/{runs} successful")

    if dm_successes > 0 and chat_successes > 0:
        logger.info("\n✅ OVERALL: LLM correctly generates new action types")
    elif dm_successes > 0 or chat_successes > 0:
        logger.info("\n⚠️ OVERALL: Partial success - some action types generated")
    else:
        logger.warning("\n❌ OVERALL: LLM did not generate expected action types")
        logger.warning("Consider adjusting prompt emphasis or action descriptions")


if __name__ == "__main__":
    asyncio.run(main())
