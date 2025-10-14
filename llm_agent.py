import json
import logging
from typing import List, Dict, Any
from datetime import datetime
from openai import OpenAI
from config import settings, CHANNEL_POOL, BOTS_POOL, WARMUP_GUIDELINES, RED_FLAGS, GREEN_FLAGS
from database import get_session_summary, get_account, get_persona, get_relevant_chats

logger = logging.getLogger(__name__)


class ActionPlannerAgent:
    """LLM-powered agent that generates natural user behavior sequences"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o-mini"
        
    def _build_prompt(self, session_id: str, account_data: Dict[str, Any] = None, persona_data: Dict[str, Any] = None) -> str:
        """
        Build the system prompt for action generation based on session history, persona, and warmup stage
        
        Args:
            session_id: Telegram session UID
            account_data: Account information from database
            persona_data: Persona information from database
            
        Returns:
            System prompt string
        """
        
        # Get account and persona if not provided
        if not account_data:
            account_data = get_account(session_id) or {}
        
        warmup_stage = account_data.get("warmup_stage", 1)
        account_id = account_data.get("id")
        
        if not persona_data and account_id:
            persona_data = get_persona(account_id)
        
        # Get warmup guidelines for current stage
        guidelines = WARMUP_GUIDELINES.get(warmup_stage, WARMUP_GUIDELINES[1])
        
        # Get relevant chats for this persona
        relevant_chats = []
        if account_id:
            relevant_chats = get_relevant_chats(account_id, limit=15)
        
        # Build channels list (mix of relevant and general)
        if relevant_chats:
            channels_list = "\n".join([
                f"- {ch['chat_username']}: {ch.get('chat_title', 'Unknown')} "
                f"(relevance: {ch.get('relevance_score', 0):.1f}) - {ch.get('relevance_reason', '')[:50]}" 
                for ch in relevant_chats[:10]
            ])
        else:
            channels_list = "\n".join([
                f"- {ch['username']}: {ch['description']}" 
                for ch in CHANNEL_POOL[:10]
            ])
        
        bots_list = "\n".join([
            f"- {bot['username']}: {bot['description']}" 
            for bot in BOTS_POOL[:5]
        ]) if BOTS_POOL else "No bots available"
        
        # Build persona context
        if persona_data:
            persona_context = f"""
ТЫ - это реальный пользователь Telegram со следующей личностью:

Имя: {persona_data.get('generated_name')}
Возраст: {persona_data.get('age')} лет
Профессия: {persona_data.get('occupation')}
Город: {persona_data.get('city')}, {persona_data.get('country')}
Интересы: {', '.join(persona_data.get('interests', []))}
Характер: {', '.join(persona_data.get('personality_traits', []))}
Стиль общения: {persona_data.get('communication_style')}
Уровень активности: {persona_data.get('activity_level')}

О тебе:
{persona_data.get('full_description', '')}

История:
{persona_data.get('background_story', '')}

ВАЖНО: Ты должен вести себя в соответствии со своей личностью. Твои действия должны отражать твои интересы, стиль общения и уровень активности.
"""
        else:
            persona_context = "Ты - обычный пользователь Telegram, который только начинает использовать мессенджер."
        
        # Build stage-specific guidance
        stage_guidance = f"""
📅 ТЕКУЩАЯ СТАДИЯ ПРОГРЕВА: День {warmup_stage} - {guidelines['description']}

ЛИМИТЫ ДЛЯ ЭТОЙ СТАДИИ:
- Максимум действий: {guidelines['max_actions']}
- Максимум вступлений в новые чаты: {guidelines['max_joins']}
- Максимум отправленных сообщений: {guidelines['max_messages']}
- Разрешенные типы действий: {', '.join(guidelines['allowed_actions'])}

РЕКОМЕНДАЦИИ:
{chr(10).join(['- ' + rec for rec in guidelines['recommendations']])}
"""
        
        # Build red/green flags
        flags_guidance = f"""
🚫 КРАСНЫЕ ФЛАГИ (ИЗБЕГАТЬ):
{chr(10).join(['- ' + flag for flag in RED_FLAGS[:5]])}

✅ ЗЕЛЕНЫЕ ФЛАГИ (ПРИОРИТЕТ):
{chr(10).join(['- ' + flag for flag in GREEN_FLAGS[:5]])}
"""
        
        return f"""{persona_context}

{stage_guidance}

{flags_guidance}

Твоя задача - сгенерировать реалистичную последовательность действий, которые ты бы совершил в Telegram СЕГОДНЯ.

Доступные каналы/чаты для взаимодействия:
{channels_list}

Доступные боты:
{bots_list}

ДОСТУПНЫЕ ТИПЫ ДЕЙСТВИЙ (выбирай только из разрешенных для текущей стадии!):

БАЗОВЫЕ ДЕЙСТВИЯ:
1. "update_profile" - Обновить профиль (имя, фото, био)
   - Params: first_name, last_name, bio
   - Только для стадий 1-3!

2. "join_channel" - Вступить в канал/группу
   - Params: channel_username
   
3. "read_messages" - Читать сообщения в канале
   - Params: channel_username, duration_seconds (3-20)
   
4. "idle" - Пауза/перерыв
   - Params: duration_seconds (2-10)

5. "view_profile" - Посмотреть профиль канала
   - Params: channel_username, duration_seconds (3-8)

ПРОДВИНУТЫЕ ДЕЙСТВИЯ (доступны с определенных стадий):
6. "react_to_message" - Поставить реакцию на сообщение
   - Params: channel_username
   - Доступно со стадии 5+
   
7. "message_bot" - Написать боту
   - Params: bot_username, message (например "/start", "/help")
   - Доступно со стадии 5+
   
8. "reply_in_chat" - Ответить на сообщение в группе
   - Params: chat_username, reply_text
   - Доступно со стадии 8+
   - LLM сгенерирует естественный ответ
   
9. "sync_contacts" - Синхронизировать контакты
   - Доступно со стадии 4+
   
10. "update_privacy" - Настроить приватность
   - Доступно со стадии 3+
   
11. "create_group" - Создать группу
   - Params: group_name
   - Доступно со стадии 10+
   
12. "forward_message" - Переслать сообщение
   - Params: from_chat, to_chat
   - Доступно со стадии 12+

КРИТИЧЕСКИ ВАЖНО:
- СТРОГО соблюдай лимиты текущей стадии!
- Используй ТОЛЬКО разрешенные типы действий
- Веди себя естественно, как реальный человек с твоей личностью
- Действуй в соответствии со своими интересами
- НЕ создавай шаблонные последовательности
- Включай паузы (idle) между действиями
- Количество действий: от {max(3, guidelines['max_actions'] - 5)} до {guidelines['max_actions']}

Пример для СТАДИИ 1 (только профиль):
[
  {{"action": "update_profile", "first_name": "{persona_data.get('generated_name', 'User').split()[0] if persona_data else 'User'}", "last_name": "{persona_data.get('generated_name', 'User').split()[-1] if persona_data else 'User'}", "bio": "Краткое описание", "reason": "Настраиваю профиль"}},
  {{"action": "idle", "duration_seconds": 5, "reason": "Осматриваюсь"}},
  {{"action": "idle", "duration_seconds": 8, "reason": "Изучаю интерфейс"}}
]

Пример для СТАДИИ 5+ (первая активность):
[
  {{"action": "view_profile", "channel_username": "@telegram", "duration_seconds": 5, "reason": "Смотрю информацию о канале"}},
  {{"action": "join_channel", "channel_username": "@telegram", "reason": "Интересный канал, вступаю"}},
  {{"action": "read_messages", "channel_username": "@telegram", "duration_seconds": 12, "reason": "Читаю последние обновления"}},
  {{"action": "react_to_message", "channel_username": "@telegram", "reason": "Понравился пост про новые функции"}},
  {{"action": "idle", "duration_seconds": 6, "reason": "Небольшой перерыв"}},
  {{"action": "message_bot", "bot_username": "@wiki", "message": "/start", "reason": "Интересно попробовать Википедия-бота"}},
  {{"action": "idle", "duration_seconds": 4, "reason": "Читаю ответ бота"}}
]

СГЕНЕРИРУЙ УНИКАЛЬНУЮ последовательность действий для СВОЕЙ личности на текущей стадии {warmup_stage}!
Формат ответа - ТОЛЬКО JSON массив объектов, без дополнительного текста!"""

    async def generate_action_plan(self, session_id: str, account_data: Dict[str, Any] = None, persona_data: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Generate a natural sequence of actions based on session history, persona, and warmup stage
        
        Args:
            session_id: The Telegram session ID
            account_data: Account information (optional, will be fetched if not provided)
            persona_data: Persona information (optional, will be fetched if not provided)
            
        Returns:
            List of actions to perform
        """
        logger.info(f"Generating action plan for session {session_id}")
        
        try:
            # Get account data if not provided
            if not account_data:
                account_data = get_account(session_id) or {}
            
            warmup_stage = account_data.get("warmup_stage", 1)
            
            # Build prompts
            system_prompt = self._build_prompt(session_id, account_data, persona_data)
            user_prompt = f"Сгенерируй последовательность действий для стадии {warmup_stage}. Будь креативным и естественным!"
            
            # Log the full conversation being sent to LLM
            logger.info("=" * 100)
            logger.info("📤 SENDING TO LLM (GPT-4o-mini)")
            logger.info("=" * 100)
            logger.info(f"SYSTEM PROMPT:\n{system_prompt}")
            logger.info("-" * 100)
            logger.info(f"USER PROMPT:\n{user_prompt}")
            logger.info("=" * 100)
            
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=2048,
                temperature=1.0,  # High temperature for diversity
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ]
            )
            
            # Extract JSON from response
            response_text = response.choices[0].message.content
            
            # Log the full LLM response
            logger.info("=" * 100)
            logger.info("📥 RECEIVED FROM LLM")
            logger.info("=" * 100)
            logger.info(f"RAW RESPONSE:\n{response_text}")
            logger.info("=" * 100)
            
            # Parse JSON (handle potential markdown code blocks)
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
                logger.info("Extracted JSON from markdown code block (```json)")
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
                logger.info("Extracted JSON from markdown code block (```)")
            else:
                json_str = response_text.strip()
                logger.info("Using raw response as JSON")
            
            actions = json.loads(json_str)
            logger.info(f"✅ Successfully parsed {len(actions)} actions from JSON")
            
            # Validate actions
            validated_actions = self._validate_actions(actions)
            
            logger.info("=" * 100)
            logger.info(f"✅ VALIDATION COMPLETE: {len(validated_actions)} / {len(actions)} actions passed")
            logger.info("=" * 100)
            for idx, action in enumerate(validated_actions, 1):
                logger.info(f"  {idx}. [{action.get('action')}] {action.get('reason', 'No reason')[:60]}")
            logger.info("=" * 100)
            
            return validated_actions
            
        except json.JSONDecodeError as e:
            logger.error("=" * 100)
            logger.error(f"❌ JSON PARSE ERROR: {e}")
            logger.error(f"Failed to parse: {response_text[:500] if 'response_text' in locals() else 'No response'}")
            logger.error("=" * 100)
            return self._get_fallback_actions()
        except Exception as e:
            logger.error("=" * 100)
            logger.error(f"❌ ERROR GENERATING ACTION PLAN: {e}")
            logger.error("=" * 100)
            return self._get_fallback_actions()
    
    def _validate_actions(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate and sanitize actions from LLM"""
        validated = []
        
        valid_actions = {
            "join_channel", "read_messages", "idle",
            "react_to_message", "message_bot", "view_profile"
        }
        
        for action in actions:
            if not isinstance(action, dict):
                continue
                
            action_type = action.get("action")
            if action_type not in valid_actions:
                logger.warning(f"Unknown action type: {action_type}, skipping")
                continue
            
            # Validate required fields
            if action_type == "join_channel":
                if "channel_username" in action:
                    validated.append(action)
                    
            elif action_type == "read_messages":
                if "channel_username" in action and "duration_seconds" in action:
                    # Cap duration at reasonable limits
                    action["duration_seconds"] = min(20, max(3, action["duration_seconds"]))
                    validated.append(action)
                    
            elif action_type == "idle":
                if "duration_seconds" in action:
                    # Cap idle time
                    action["duration_seconds"] = min(10, max(2, action["duration_seconds"]))
                    validated.append(action)
                    
            elif action_type == "react_to_message":
                if "channel_username" in action:
                    # Emoji is optional - system will pick one automatically
                    # Remove emoji if LLM provided it (we don't use it anymore)
                    if "emoji" in action:
                        del action["emoji"]
                    validated.append(action)
                        
            elif action_type == "message_bot":
                if "bot_username" in action and "message" in action:
                    # Sanitize message length
                    action["message"] = action["message"][:200]  # Max 200 chars
                    validated.append(action)
                    
            elif action_type == "view_profile":
                if "channel_username" in action:
                    # Add duration if missing
                    if "duration_seconds" not in action:
                        action["duration_seconds"] = 5
                    action["duration_seconds"] = min(8, max(3, action["duration_seconds"]))
                    validated.append(action)
        
        # Ensure we have at least some actions
        if len(validated) < 3:
            logger.warning("Too few valid actions, using fallback")
            return self._get_fallback_actions()
        
        return validated
    
    def _get_fallback_actions(self) -> List[Dict[str, Any]]:
        """Return a safe fallback sequence if LLM fails"""
        return [
            {
                "action": "join_channel",
                "channel_username": "@telegram",
                "reason": "Join official Telegram channel"
            },
            {
                "action": "read_messages",
                "channel_username": "@telegram",
                "duration_seconds": 8,
                "reason": "Browse official updates"
            },
            {
                "action": "idle",
                "duration_seconds": 5,
                "reason": "Short break"
            },
            {
                "action": "join_channel",
                "channel_username": "@durov",
                "reason": "Join Pavel Durov's channel"
            },
            {
                "action": "read_messages",
                "channel_username": "@durov",
                "duration_seconds": 10,
                "reason": "Read posts"
            }
        ]

