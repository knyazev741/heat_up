"""
ChatContextAnalyzer - LLM-powered analysis of group chat context before responding.

This module provides:
1. Analysis of recent messages in a group chat
2. Determination of current discussion topic
3. Assessment of whether it's appropriate to respond
4. Generation of context-aware responses

Part of Phase 2: Real group chat participation.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from openai import OpenAI
from config import settings

logger = logging.getLogger(__name__)


class ChatContextAnalyzer:
    """
    Analyzes group chat context to determine appropriate responses.

    Used before sending messages to real public groups to ensure
    natural, contextual participation.
    """

    def __init__(self):
        self.client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com"
        )
        self.model = "deepseek-chat"

    async def analyze_chat_context(
        self,
        messages: List[Dict[str, Any]],
        persona: Dict[str, Any],
        chat_info: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Analyze recent messages in a chat to determine if and how to respond.

        Args:
            messages: List of recent messages from the chat
            persona: Account's persona data
            chat_info: Optional chat metadata (title, type, etc.)

        Returns:
            Analysis result with:
            - should_respond: bool - whether it's appropriate to respond
            - topic: str - current discussion topic
            - tone: str - chat tone (formal/informal)
            - response_type: str - type of response suggested
            - target_message_id: int - message to reply to (if any)
            - suggested_response: str - generated response text
            - confidence: float - confidence in the analysis (0-1)
            - reason: str - explanation of the decision
        """
        if not messages:
            return {
                "should_respond": False,
                "reason": "No messages to analyze",
                "confidence": 0.0
            }

        # Format messages for LLM
        formatted_messages = self._format_messages(messages)

        # Build persona context
        persona_context = self._build_persona_context(persona)

        # Build chat context
        chat_context = ""
        if chat_info:
            chat_context = f"""
Информация о чате:
- Название: {chat_info.get('title', 'Unknown')}
- Тип: {chat_info.get('type', 'group')}
- Участников: {chat_info.get('member_count', 'неизвестно')}
"""

        prompt = f"""Ты анализируешь групповой чат в Telegram чтобы определить, стоит ли человеку вступить в разговор.

{persona_context}

{chat_context}

ПОСЛЕДНИЕ СООБЩЕНИЯ В ЧАТЕ:
{formatted_messages}

ТВОЯ ЗАДАЧА:
1. Определи текущую тему обсуждения
2. Оцени тон общения (формальный/неформальный/дружеский/агрессивный)
3. Определи, есть ли вопрос или тема, на которую можно ответить
4. Реши, уместно ли сейчас вступить в разговор этому человеку
5. Если да - предложи ЕСТЕСТВЕННЫЙ ответ

КРИТЕРИИ ДЛЯ ОТВЕТА:
✅ Отвечать уместно если:
- Обсуждается тема, в которой персона разбирается
- Кто-то задал вопрос по теме интересов персоны
- Можно поддержать разговор естественным образом
- Прошло достаточно времени с последнего сообщения (>2 мин)

❌ НЕ отвечать если:
- Обсуждается личная тема между конкретными людьми
- Идёт конфликт или спор
- Тема не связана с интересами персоны
- Слишком активное обсуждение (много сообщений за минуту)
- Последнее сообщение было только что (<1 мин назад)

ФОРМАТ ОТВЕТА - JSON:
{{
    "should_respond": true/false,
    "topic": "текущая тема обсуждения",
    "tone": "informal/formal/friendly/hostile",
    "activity_level": "low/medium/high",
    "response_type": "answer/opinion/question/support/none",
    "target_message_id": null или ID сообщения для reply,
    "suggested_response": "текст ответа" или null,
    "confidence": 0.0-1.0,
    "reason": "объяснение решения"
}}

ВАЖНО:
- Ответ должен быть ЕСТЕСТВЕННЫМ, на русском языке
- Не используй канцелярит и шаблонные фразы
- Учитывай стиль общения персоны
- Если отвечаешь - ответ должен быть по делу, краткий (1-3 предложения)

ТОЛЬКО JSON!"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=0.7,
                max_tokens=800,
                messages=[
                    {"role": "system", "content": "Ты эксперт по анализу социальных взаимодействий в мессенджерах. Отвечай только JSON."},
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = response.choices[0].message.content

            # Parse JSON
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text.strip()

            result = json.loads(json_str)

            # Validate and sanitize
            result = self._validate_analysis(result, messages)

            logger.info(f"Chat analysis: should_respond={result.get('should_respond')}, "
                       f"topic='{result.get('topic', '')[:50]}', confidence={result.get('confidence', 0):.2f}")

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse chat analysis JSON: {e}")
            return {
                "should_respond": False,
                "reason": "Analysis failed - JSON parse error",
                "confidence": 0.0
            }
        except Exception as e:
            logger.error(f"Error analyzing chat context: {e}")
            return {
                "should_respond": False,
                "reason": f"Analysis failed - {str(e)}",
                "confidence": 0.0
            }

    async def generate_contextual_response(
        self,
        messages: List[Dict[str, Any]],
        persona: Dict[str, Any],
        target_message_id: Optional[int] = None,
        topic_hint: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate a contextual response based on chat history.

        Args:
            messages: Recent messages from the chat
            persona: Account's persona
            target_message_id: Specific message to reply to
            topic_hint: Optional topic to focus on

        Returns:
            Generated response text or None
        """
        if not messages:
            return None

        formatted_messages = self._format_messages(messages)
        persona_context = self._build_persona_context(persona)

        target_context = ""
        if target_message_id:
            target_msg = next((m for m in messages if m.get('id') == target_message_id), None)
            if target_msg:
                target_context = f"\nОТВЕЧАЕШЬ НА СООБЩЕНИЕ: \"{target_msg.get('text', '')[:200]}\""

        topic_context = ""
        if topic_hint:
            topic_context = f"\nТЕМА РАЗГОВОРА: {topic_hint}"

        prompt = f"""{persona_context}

ПОСЛЕДНИЕ СООБЩЕНИЯ В ЧАТЕ:
{formatted_messages}
{target_context}
{topic_context}

ТВОЯ ЗАДАЧА:
Напиши ОДНО естественное сообщение в этот чат.

ПРАВИЛА:
1. Сообщение должно быть релевантным текущему разговору
2. Используй СВОЙ стиль общения (из персоны)
3. Будь кратким - 1-3 предложения максимум
4. Не повторяй то, что уже сказали другие
5. Можно:
   - Ответить на вопрос если знаешь ответ
   - Поделиться мнением по теме
   - Задать уточняющий вопрос
   - Поддержать чью-то идею
6. НЕ НУЖНО:
   - Представляться ("Привет, я Маша...")
   - Использовать канцелярит
   - Писать слишком формально
   - Использовать много эмодзи

ВЕРНИ ТОЛЬКО ТЕКСТ СООБЩЕНИЯ (без кавычек, без JSON):"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=0.9,
                max_tokens=200,
                messages=[
                    {"role": "system", "content": "Ты - человек, участвующий в групповом чате Telegram. Отвечай естественно, по-русски."},
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = response.choices[0].message.content.strip()

            # Clean up response
            response_text = response_text.strip('"\'')

            # Validate response
            if len(response_text) < 3:
                logger.warning("Generated response too short")
                return None

            if len(response_text) > 500:
                response_text = response_text[:500]

            # Check for spam patterns
            spam_patterns = ['заработок', 'инвестиц', 'бесплатно', 'скидк', 'акция',
                           'http://', 'https://', 't.me/', '@']
            if any(p in response_text.lower() for p in spam_patterns):
                logger.warning(f"Generated response contains spam pattern: {response_text[:50]}")
                return None

            logger.info(f"Generated contextual response: {response_text[:80]}...")
            return response_text

        except Exception as e:
            logger.error(f"Error generating contextual response: {e}")
            return None

    def _format_messages(self, messages: List[Dict[str, Any]], limit: int = 30) -> str:
        """Format messages for LLM prompt"""
        lines = []

        # Sort by ID (chronological order)
        sorted_messages = sorted(messages[-limit:], key=lambda m: m.get('id', 0))

        for msg in sorted_messages:
            sender = msg.get('sender_name') or msg.get('from_name') or 'Unknown'
            text = msg.get('text') or msg.get('message') or ''
            msg_id = msg.get('id', '?')

            # Get timestamp if available
            timestamp = msg.get('date') or msg.get('timestamp')
            time_str = ""
            if timestamp:
                if isinstance(timestamp, str):
                    time_str = f" [{timestamp[-8:]}]"  # Last 8 chars (HH:MM:SS)
                elif isinstance(timestamp, (int, float)):
                    dt = datetime.fromtimestamp(timestamp)
                    time_str = f" [{dt.strftime('%H:%M')}]"

            if text:
                # Truncate very long messages
                if len(text) > 300:
                    text = text[:300] + "..."
                lines.append(f"[#{msg_id}]{time_str} {sender}: {text}")
            else:
                media_type = msg.get('media_type', 'media')
                lines.append(f"[#{msg_id}]{time_str} {sender}: [{media_type}]")

        return "\n".join(lines)

    def _build_persona_context(self, persona: Dict[str, Any]) -> str:
        """Build persona description for prompts"""
        if not persona:
            return "Ты - обычный пользователь Telegram."

        return f"""ТЫ - {persona.get('generated_name', 'Пользователь')}, {persona.get('age', 25)} лет.
Профессия: {persona.get('occupation', 'не указана')}
Интересы: {', '.join(persona.get('interests', ['общение']))}
Стиль общения: {persona.get('communication_style', 'дружелюбный')}
Характер: {', '.join(persona.get('personality_traits', ['общительный']))}"""

    def _validate_analysis(
        self,
        result: Dict[str, Any],
        messages: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Validate and sanitize analysis result"""

        # Ensure required fields
        if 'should_respond' not in result:
            result['should_respond'] = False

        if 'confidence' not in result:
            result['confidence'] = 0.5

        # Validate confidence range
        result['confidence'] = max(0.0, min(1.0, float(result.get('confidence', 0.5))))

        # If confidence too low, don't respond
        if result['confidence'] < 0.5 and result['should_respond']:
            result['should_respond'] = False
            result['reason'] = f"Confidence too low ({result['confidence']:.2f})"

        # Validate target_message_id
        if result.get('target_message_id'):
            valid_ids = [m.get('id') for m in messages if m.get('id')]
            if result['target_message_id'] not in valid_ids:
                result['target_message_id'] = None

        # Sanitize suggested response
        if result.get('suggested_response'):
            response = result['suggested_response']

            # Remove quotes if wrapped
            response = response.strip('"\'')

            # Check length
            if len(response) < 3:
                result['suggested_response'] = None
            elif len(response) > 500:
                result['suggested_response'] = response[:500]
            else:
                result['suggested_response'] = response

        return result

    async def should_participate_in_chat(
        self,
        chat_info: Dict[str, Any],
        persona: Dict[str, Any],
        recent_activity: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Determine if the account should actively participate in a specific chat.

        Args:
            chat_info: Chat metadata
            persona: Account's persona
            recent_activity: Account's recent activity stats

        Returns:
            Decision with reasoning
        """
        chat_title = chat_info.get('title', '')
        chat_type = chat_info.get('type', 'group')
        member_count = chat_info.get('member_count', 0)
        interests = persona.get('interests', [])

        # Basic checks
        reasons = []
        score = 0.5

        # Type check - prefer groups over channels
        if chat_type in ['group', 'supergroup']:
            score += 0.2
            reasons.append("Групповой чат - можно общаться")
        elif chat_type == 'channel':
            score -= 0.3
            reasons.append("Канал - только чтение")

        # Size check
        if member_count:
            if 10 <= member_count <= 1000:
                score += 0.1
                reasons.append(f"Оптимальный размер ({member_count} участников)")
            elif member_count > 5000:
                score -= 0.1
                reasons.append(f"Очень большой чат ({member_count})")

        # Interest relevance (simple keyword matching)
        chat_title_lower = chat_title.lower()
        matching_interests = [i for i in interests if i.lower() in chat_title_lower]
        if matching_interests:
            score += 0.2
            reasons.append(f"Совпадение интересов: {', '.join(matching_interests)}")

        # Recent activity check
        if recent_activity:
            messages_sent_today = recent_activity.get('messages_sent_today', 0)
            if messages_sent_today >= 5:
                score -= 0.2
                reasons.append(f"Уже много сообщений сегодня ({messages_sent_today})")

        should_participate = score >= 0.5

        return {
            "should_participate": should_participate,
            "score": score,
            "reasons": reasons,
            "chat_title": chat_title
        }
