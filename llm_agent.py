import json
import logging
from typing import List, Dict, Any
from datetime import datetime
from openai import OpenAI
from config import settings, CHANNEL_POOL, BOTS_POOL, WARMUP_GUIDELINES, RED_FLAGS, GREEN_FLAGS
from database import get_session_summary, get_session_history, get_account, get_persona, get_relevant_chats

logger = logging.getLogger(__name__)


class ActionPlannerAgent:
    """LLM-powered agent that generates natural user behavior sequences"""
    
    def __init__(self):
        # Using DeepSeek API (OpenAI-compatible)
        self.client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com"
        )
        self.model = "deepseek-chat"  # DeepSeek model for better cost efficiency
        
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
        
        # Get session history (последние 3 сеанса)
        session_summary = get_session_summary(session_id, days=7)
        recent_history = get_session_history(session_id, days=7)
        
        # Get relevant chats for this persona
        relevant_chats = []
        if account_id:
            all_chats = get_relevant_chats(account_id, limit=50)
            logger.info(f"📊 get_relevant_chats({account_id}) returned {len(all_chats)} chats")
            # ФИЛЬТР: ТОЛЬКО каналы с relevance_score >= 0.4
            relevant_chats = [ch for ch in all_chats if ch.get('relevance_score', 0) >= 0.4]
            logger.info(f"📊 After filtering (>=0.4): {len(relevant_chats)} chats")
            if relevant_chats:
                for i, ch in enumerate(relevant_chats[:5]):
                    logger.info(f"  {i+1}. {ch.get('chat_username')} (score: {ch.get('relevance_score', 0):.2f})")
        
        # Build channels list (ТОЛЬКО релевантные!) с маркерами [ВСТУПИЛ] / [НОВЫЙ]
        if relevant_chats:
            channels_list = "\n".join([
                f"- {ch['chat_username']}: {ch.get('chat_title', 'Unknown')} "
                f"[{(ch.get('chat_type') or 'unknown').upper()}] "
                f"{'[ВСТУПИЛ ✅]' if ch.get('is_joined') else '[НОВЫЙ]'} "
                f"(релевантность: {ch.get('relevance_score', 0):.1f}) - {ch.get('relevance_reason', '')[:80]}"
                for ch in relevant_chats[:15]
            ])
            logger.info(f"✅ Using {len(relevant_chats[:15])} RELEVANT chats from discovered_chats")
            logger.info(f"📝 Channels list:\n{channels_list[:300]}...")
            
            # Статистика по joined/not joined
            joined_count = sum(1 for ch in relevant_chats if ch.get('is_joined'))
            not_joined_count = len(relevant_chats) - joined_count
            logger.info(f"📊 Joined: {joined_count}, Not joined: {not_joined_count}")
        else:
            # Если НЕТ релевантных - используем общие, но БЕЗ @telegram/@durov
            fallback_channels = [ch for ch in CHANNEL_POOL if ch['username'] not in ['@telegram', '@durov']]
            channels_list = "\n".join([
                f"- {ch['username']}: {ch['description']}" 
                for ch in fallback_channels[:10]
            ])
            logger.warning(f"⚠️ NO relevant chats! Using fallback: {len(fallback_channels[:10])} channels")
        
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
            persona_context = """Ты - обычный пользователь Telegram, который только начинает использовать мессенджер.

⚠️ ВАЖНО: Ты НЕ робот! Ты реальный человек со своими особенностями:
- У тебя может быть необычный ник, псевдоним или вообще без имени в профиле
- Ты можешь НЕ заполнять все поля профиля (многие так и делают)
- Твоё поведение должно быть УНИКАЛЬНЫМ, не шаблонным
- Каждый человек действует ПО-РАЗНОМУ - будь креативен!

📊 ПРИМЕРЫ РЕАЛЬНОГО ПОВЕДЕНИЯ ЛЮДЕЙ В TELEGRAM:
- Кто-то ставит просто "А" или "K" в имени
- Кто-то использует эмодзи: "🌙 Luna" или "Phoenix 🔥"
- Кто-то пишет псевдоним: "Клеопатра", "Аврора", "Зевс"
- Кто-то оставляет пустые поля и пользуется анонимно
- Кто-то ставит уменьшительное: "Маша" вместо "Мария"
- НО НИКТО не пишет шаблонно "Имя Фамилия" как в паспорте!"""
        
        # Check if account is brand new (NO history at all)
        is_brand_new = not recent_history or len(recent_history) == 0
        
        # Check if profile was EVER updated (across ALL history)
        has_updated_profile = False
        if recent_history:
            has_updated_profile = any(
                action.get('action_type') == 'update_profile' 
                for action in recent_history
            )
            logger.info(f"🔍 Profile update check for {session_id}: has_updated_profile={has_updated_profile} (checked {len(recent_history)} actions)")
        
        if is_brand_new:
            persona_context += "\n\n⚠️⚠️⚠️ КРИТИЧЕСКИ ВАЖНО ⚠️⚠️⚠️\nЭТО ТВОЙ ПЕРВЫЙ СЕАНС! У тебя НЕТ истории активности.\n❌ НЕ обновляй профиль (update_profile)! Telegram банит за это свежие аккаунты!\n✅ Начни с простых действий: просмотр каналов (view_profile), чтение (read_messages), паузы (idle)"
        
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
        
        # Build history context
        history_context = ""
        if recent_history:
            import json
            from datetime import datetime
            
            # Группируем по сеансам (примерно по времени)
            sessions_grouped = []
            current_session = []
            last_time = None
            
            for action in reversed(recent_history[-15:]):  # Последние 15 действий
                action_time = datetime.fromisoformat(action['timestamp'])
                
                if last_time and (action_time - last_time).total_seconds() > 3600:
                    # Больше часа - новый сеанс
                    if current_session:
                        sessions_grouped.append(current_session)
                    current_session = []
                
                current_session.append(action)
                last_time = action_time
            
            if current_session:
                sessions_grouped.append(current_session)
            
            # Берем последние 3 сеанса
            recent_sessions = sessions_grouped[-3:]
            
            history_lines = []
            for i, session in enumerate(recent_sessions, 1):
                if session:
                    first_action_time = datetime.fromisoformat(session[0]['timestamp'])
                    time_ago = datetime.utcnow() - first_action_time
                    
                    if time_ago.days > 0:
                        time_str = f"{time_ago.days} дн. назад"
                    elif time_ago.seconds > 3600:
                        time_str = f"{time_ago.seconds // 3600} ч. назад"
                    else:
                        time_str = f"{time_ago.seconds // 60} мин. назад"
                    
                    history_lines.append(f"\nСеанс {i} ({time_str}):")
                    
                    for action in session[:5]:  # До 5 действий на сеанс
                        try:
                            # action_data уже dict (database.py конвертирует автоматически)
                            data = action['action_data'] if action['action_data'] else {}
                            action_type = action['action_type']
                            
                            if action_type == 'update_profile':
                                bio = data.get('bio', '')[:50]
                                history_lines.append(f"  - Обновил профиль{': ' + bio if bio else ''}")
                            elif action_type == 'join_channel':
                                channel = data.get('channel_username', '')
                                history_lines.append(f"  - Вступил в {channel}")
                            elif action_type == 'view_profile':
                                channel = data.get('channel_username', '')
                                history_lines.append(f"  - Просмотрел {channel}")
                            elif action_type == 'read_messages':
                                channel = data.get('channel_username', '')
                                history_lines.append(f"  - Читал {channel}")
                            elif action_type == 'idle':
                                duration = data.get('duration_seconds', 0)
                                history_lines.append(f"  - Пауза ({duration}с)")
                            else:
                                history_lines.append(f"  - {action_type}")
                        except:
                            pass
            
            if history_lines:
                history_context = f"""
📜 ТВОЯ ПОСЛЕДНЯЯ АКТИВНОСТЬ:
{chr(10).join(history_lines)}

⚠️ НЕ ПОВТОРЯЙ предыдущие действия! Если ты уже обновлял профиль - НЕ обновляй его снова.
⚠️ Если уже вступал в канал - ВСТУПИ В ДРУГОЙ или ЧИТАЙ сообщения в нем.
⚠️ Веди себя РАЗНООБРАЗНО, как настоящий человек!
"""
        
        # ДИНАМИЧЕСКИЙ СПИСОК ДЕЙСТВИЙ - в зависимости от истории
        actions_list = []
        action_num = 1
        
        # update_profile - ПОЛНОСТЬЮ УДАЛЕНО (замороженные аккаунты)
        logger.info(f"🚫 update_profile ОТКЛЮЧЕН глобально (вызывает заморозку аккаунтов)")
        
        # Остальные действия - всегда доступны
        actions_list.append(f"""
{action_num}. join_channel (join_chat):
   {{"action": "join_channel", "channel_username": "@example", "reason": "Интересная тематика"}}""")
        action_num += 1
        
        actions_list.append(f"""
{action_num}. read_messages:
   {{"action": "read_messages", "channel_username": "@example", "duration_seconds": 15, "reason": "Читаю контент"}}""")
        action_num += 1
        
        actions_list.append(f"""
{action_num}. idle:
   {{"action": "idle", "duration_seconds": 7, "reason": "Короткая пауза"}}""")
        action_num += 1
        
        actions_list.append(f"""
{action_num}. view_profile:
   {{"action": "view_profile", "channel_username": "@example", "duration_seconds": 5, "reason": "Изучаю чат/канал"}}""")
        
        basic_actions = "\n".join(actions_list)
        
        # Формируем полный return с динамическим списком действий
        return f"""{persona_context}

{stage_guidance}

{flags_guidance}
{history_context}

Твоя задача - сгенерировать реалистичную последовательность действий, которые ты бы совершил в Telegram СЕГОДНЯ.

📋 ДОСТУПНЫЕ ЧАТЫ/КАНАЛЫ (подобраны СПЕЦИАЛЬНО для ТВОИХ интересов):
{channels_list}

⚠️ КРИТИЧЕСКИ ВАЖНО:
- Используй ТОЛЬКО чаты/каналы из списка выше!
- Выбирай варианты с ВЫСОКОЙ релевантностью (>0.7) в первую очередь
- НЕ используй @telegram или @durov - это слишком очевидно
- Каждый человек вступает в РАЗНЫЕ чаты/каналы, соответствующие СВОИМ интересам!

🔴 ПОНИМАНИЕ МЕТОК:
- [ВСТУПИЛ ✅] - ты УЖЕ вступил в этот чат/канал! Можешь ЧИТАТЬ сообщения (read_messages) или ставить реакции
- [НОВЫЙ] - ты ЕЩЁ НЕ вступил! Сначала нужно ВСТУПИТЬ (join_channel), потом читать
- НЕ пытайся читать сообщения там, где ты ещё не вступил!

🤖 Доступные боты:
{bots_list}

ДОСТУПНЫЕ ТИПЫ ДЕЙСТВИЙ (выбирай только из разрешенных для текущей стадии!):

БАЗОВЫЕ ДЕЙСТВИЯ (JSON формат - БЕЗ вложенного "params"!):
{basic_actions}

ПРОДВИНУТЫЕ ДЕЙСТВИЯ (доступны с определенных стадий):
6. "react_to_message" - Поставить реакцию на сообщение
   - Params: channel_username (или chat_username)
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

⚠️ КРИТИЧЕСКИ ВАЖНО - ВЫБОР КАНАЛОВ:
- ИСПОЛЬЗУЙ ТОЛЬКО каналы из списка "Доступные каналы/чаты" выше
- ПРИОРИТЕТ №1: Группы ГОРОДА с высокой релевантностью (chat_type: group)
- ПРИОРИТЕТ №2: Тематические группы по ИНТЕРЕСАМ персоны
- НИКОГДА не придумывай username сам - ТОЛЬКО из списка!
- Выбирай каналы с ВЫСОКОЙ релевантностью (0.8+)
- Чем выше relevance_score - тем лучше подходит канал

🎯 ТВОЯ ЗАДАЧА:
1. Посмотри на СВОИ интересы: {', '.join(persona_data.get('interests', [])) if persona_data else 'общие'}
2. Выбери каналы из списка выше, которые соответствуют ТВОИМ интересам (с высокой релевантностью)
3. Сгенерируй УНИКАЛЬНУЮ последовательность, НЕ ПОХОЖУЮ на примеры
4. Каждый человек действует ПО-РАЗНОМУ - варьируй порядок, каналы, длительности!

Стадия: {warmup_stage}
Формат ответа - ТОЛЬКО JSON массив, без текста!"""

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
            "update_profile", "join_channel", "read_messages", "idle",
            "react_to_message", "message_bot", "view_profile",
            "reply_in_chat", "sync_contacts", "update_privacy",
            "create_group", "forward_message"
        }
        
        for action in actions:
            if not isinstance(action, dict):
                continue
                
            action_type = action.get("action")
            if action_type not in valid_actions:
                logger.warning(f"Unknown action type: {action_type}, skipping")
                continue
            
            # Validate required fields
            if action_type == "update_profile":
                # Проверяем на типичные шаблонные сочетания
                first_name = action.get('first_name', '')
                last_name = action.get('last_name', '')
                
                # Список ЗАПРЕЩЕННЫХ шаблонных сочетаний
                forbidden_combinations = [
                    ('Алексей', 'Иванов'), ('Иван', 'Петров'), ('Екатерина', 'Смирнова'),
                    ('Александр', 'Кузнецов'), ('Дмитрий', 'Попов'), ('Михаил', 'Соколов'),
                    ('Андрей', 'Новиков'), ('Сергей', 'Морозов'), ('Николай', 'Волков'),
                    ('Мария', 'Петрова'), ('Анна', 'Иванова'), ('Елена', 'Смирнова'),
                    ('Ольга', 'Кузнецова'), ('Наталья', 'Попова'), ('Татьяна', 'Соколова')
                ]
                
                # Проверка
                is_forbidden = (first_name, last_name) in forbidden_combinations
                
                if is_forbidden and first_name and last_name:
                    logger.warning(f"🚫 BLOCKED template combination: {first_name} {last_name}")
                    # Убираем фамилию, оставляем только имя
                    action['last_name'] = ''
                    logger.info(f"✅ Fixed to: {first_name} (без фамилии)")
                
                validated.append(action)
                    
            elif action_type in {"join_channel", "join_chat"}:
                username = action.get("chat_username") or action.get("channel_username")
                if username:
                    action["chat_username"] = username
                    action["channel_username"] = username
                    action["action"] = "join_channel"
                    validated.append(action)

            elif action_type in {"read_messages", "read_chat_messages"}:
                username = action.get("chat_username") or action.get("channel_username")
                if username and "duration_seconds" in action:
                    action["chat_username"] = username
                    action["channel_username"] = username
                    action["action"] = "read_messages"
                    action["duration_seconds"] = min(20, max(3, action["duration_seconds"]))
                    validated.append(action)
                    
            elif action_type == "idle":
                if "duration_seconds" in action:
                    # Cap idle time
                    action["duration_seconds"] = min(10, max(2, action["duration_seconds"]))
                    validated.append(action)
                    
            elif action_type == "react_to_message":
                username = action.get("chat_username") or action.get("channel_username")
                if username:
                    action["chat_username"] = username
                    action["channel_username"] = username
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
                username = action.get("chat_username") or action.get("channel_username")
                if username:
                    action["chat_username"] = username
                    action["channel_username"] = username
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
        """Return a safe fallback sequence if LLM fails - ТОЛЬКО idle действия"""
        logger.warning("⚠️ USING FALLBACK ACTIONS - LLM generation failed!")
        return [
            {
                "action": "idle",
                "duration_seconds": 10,
                "reason": "Waiting"
            },
            {
                "action": "idle",
                "duration_seconds": 8,
                "reason": "Thinking"
            },
            {
                "action": "idle",
                "duration_seconds": 12,
                "reason": "Short break"
            }
        ]

