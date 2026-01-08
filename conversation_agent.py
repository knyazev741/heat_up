"""
Conversation Agent

LLM-powered agent for generating natural conversation messages between bots.
Uses DeepSeek API for cost-efficient message generation.
"""

import json
import logging
import re
from typing import Dict, Any, Optional, List
from openai import OpenAI
from config import settings

logger = logging.getLogger(__name__)


# Prompts for conversation generation
CONVERSATION_STARTER_PROMPT = """Ты — {my_name}, {my_age} лет, {my_occupation}.
Твой стиль общения: {my_style}
Твои интересы: {my_interests}

Ты хочешь начать переписку с человеком:
- Имя: {their_name}
- Возраст: {their_age}
- Профессия: {their_occupation}
- Интересы: {their_interests}

ОБЩИЙ КОНТЕКСТ (как вы могли познакомиться):
{common_context}

ТВОЯ ЗАДАЧА:
Напиши ПЕРВОЕ сообщение для начала диалога.

ПРАВИЛА:
1. Сообщение должно быть естественным поводом написать
2. Не представляйся формально ("Привет, я Иван")
3. Можно:
   - Сослаться на общий чат/интерес
   - Задать вопрос по теме интересов собеседника
   - Поделиться чем-то релевантным
4. Длина: 1-3 предложения
5. Тон: дружелюбный, неформальный
6. Пиши на русском языке

ПРИМЕРЫ ХОРОШИХ СТАРТЕРОВ:
- "Привет! Видел тебя в чате про крипту, ты там писал про стейкинг. Сам думаю попробовать, есть опыт?"
- "О, ты тоже из Питера? Как там погода сейчас?"
- "Привет! Случайно заметил твой коммент про Python, сам учу сейчас. Давно в этом?"

ВЕРНИ ТОЛЬКО ТЕКСТ СООБЩЕНИЯ (без кавычек):"""

CONVERSATION_RESPONSE_PROMPT = """Ты — {my_name}, {my_age} лет, {my_occupation}.
Характер: {my_traits}
Стиль общения: {my_style}
Интересы: {my_interests}

СОБЕСЕДНИК:
{their_name}, {their_age} лет, {their_occupation}
Интересы: {their_interests}

ИСТОРИЯ ПЕРЕПИСКИ:
{conversation_history}

ТЕКУЩАЯ ТЕМА: {current_topic}

ТВОЯ ЗАДАЧА:
Напиши ответ на последнее сообщение.

ПРАВИЛА:
1. Отвечай как живой человек в мессенджере
2. Учитывай контекст всей переписки
3. Можешь:
   - Отвечать на вопросы
   - Задавать свои вопросы
   - Делиться мнением/опытом
   - Использовать эмодзи (умеренно, 0-2 штуки)
   - Шутить если уместно
4. Длина: 1-4 предложения
5. НЕ НАДО:
   - Писать слишком формально
   - Использовать канцелярит
   - Повторять то что уже говорил
   - Резко менять тему
6. Пиши на русском языке

ВЕРНИ ТОЛЬКО ТЕКСТ СООБЩЕНИЯ (без кавычек):"""

CONVERSATION_CLOSING_PROMPT = """Ты — {my_name}, {my_style} стиль общения.

Тебе нужно естественно завершить диалог с собеседником.

ПОСЛЕДНИЕ СООБЩЕНИЯ:
{recent_messages}

ТВОЯ ЗАДАЧА:
Напиши завершающее сообщение.

ПРАВИЛА:
1. Будь естественным и дружелюбным
2. Можно:
   - "Ладно, пойду. Было приятно поболтать!"
   - "Окей, мне пора. Увидимся!"
   - "Хорошо, удачи! Напишу как будет время"
3. Длина: 1-2 предложения
4. НЕ надо писать "До свидания" или слишком формально
5. Пиши на русском языке

ВЕРНИ ТОЛЬКО ТЕКСТ СООБЩЕНИЯ (без кавычек):"""


GROUP_MESSAGE_PROMPT = """Ты — {my_name}, {my_age} лет, {my_occupation}.
Характер: {my_traits}
Стиль общения: {my_style}
Интересы: {my_interests}

ТЫ ПИШЕШЬ В ГРУППОВОЙ ЧАТ "{group_type}".
Тема группы: {group_topic}

УЧАСТНИКИ ГРУППЫ:
{members_info}

ПОСЛЕДНИЕ СООБЩЕНИЯ В ГРУППЕ:
{recent_messages}

ТВОЯ ЗАДАЧА:
Напиши сообщение в групповой чат.

ПРАВИЛА:
1. Сообщение должно быть естественным для группового чата
2. Можно:
   - Отвечать на чье-то сообщение (без @-упоминаний)
   - Задавать вопрос группе
   - Делиться мыслью/новостью по теме
   - Шутить если уместно
   - Использовать эмодзи (0-2 штуки)
3. НЕ надо:
   - Писать @username
   - Здороваться каждый раз
   - Писать слишком формально
   - Спамить вопросами
4. Длина: 1-3 предложения
5. Пиши на русском языке

ПРИМЕРЫ ХОРОШИХ СООБЩЕНИЙ:
- "А что вы думаете про новый сезон?"
- "Кстати, вчера видел интересную статью про это"
- "Согласен, я тоже так думаю"
- "Ого, серьезно? Не знал об этом"
- "Хаха, это точно 😄"

ВЕРНИ ТОЛЬКО ТЕКСТ СООБЩЕНИЯ (без кавычек):"""


GROUP_STARTER_PROMPT = """Ты — {my_name}, {my_age} лет, {my_occupation}.
Стиль общения: {my_style}
Интересы: {my_interests}

ТЫ ПЕРВЫЙ ПИШЕШЬ В НОВЫЙ ГРУППОВОЙ ЧАТ "{group_type}".
Тема группы: {group_topic}

УЧАСТНИКИ ГРУППЫ:
{members_info}

ТВОЯ ЗАДАЧА:
Напиши первое сообщение для оживления чата.

ПРАВИЛА:
1. Начни разговор естественно
2. Можно:
   - Предложить обсудить что-то по теме
   - Задать вопрос группе
   - Поделиться чем-то интересным
3. НЕ надо:
   - Формально приветствовать всех
   - Писать "Привет всем!"
   - Спрашивать "Как дела?"
4. Длина: 1-2 предложения
5. Пиши на русском языке

ПРИМЕРЫ:
- "Кто-нибудь смотрел вчерашний матч?"
- "Слушайте, а что скажете про..."
- "Видели новость про...? Интересно ваше мнение"

ВЕРНИ ТОЛЬКО ТЕКСТ СООБЩЕНИЯ (без кавычек):"""


class ConversationAgent:
    """LLM agent for generating conversation messages"""

    def __init__(self):
        self.client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com"
        )
        self.model = "deepseek-chat"

    async def generate_conversation_starter(
        self,
        my_persona: Dict[str, Any],
        their_persona: Dict[str, Any],
        common_context: str = None
    ) -> Optional[str]:
        """
        Generate the first message to start a conversation

        Args:
            my_persona: Persona of the initiator
            their_persona: Persona of the responder
            common_context: Context for how they might have met

        Returns:
            Starter message text or None
        """
        # Find common interests if no context provided
        if not common_context:
            my_interests = set(my_persona.get("interests", []))
            their_interests = set(their_persona.get("interests", []))
            common_interests = my_interests & their_interests

            if common_interests:
                common_context = f"Общие интересы: {', '.join(list(common_interests)[:3])}"
            else:
                common_context = "Случайное знакомство в Telegram"

        prompt = CONVERSATION_STARTER_PROMPT.format(
            my_name=my_persona.get("generated_name", "Аноним"),
            my_age=my_persona.get("age", 25),
            my_occupation=my_persona.get("occupation", "не указано"),
            my_style=my_persona.get("communication_style", "дружелюбный"),
            my_interests=", ".join(my_persona.get("interests", ["общение"])),
            their_name=their_persona.get("generated_name", "Собеседник"),
            their_age=their_persona.get("age", 25),
            their_occupation=their_persona.get("occupation", "не указано"),
            their_interests=", ".join(their_persona.get("interests", ["общение"])),
            common_context=common_context
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=150,
                temperature=0.9,
                messages=[
                    {"role": "system", "content": "Ты генерируешь естественные сообщения для Telegram чата. Отвечай ТОЛЬКО текстом сообщения."},
                    {"role": "user", "content": prompt}
                ]
            )

            text = response.choices[0].message.content.strip()
            validated = self._validate_message(text)

            if validated:
                logger.info(f"Generated starter: {validated[:50]}...")
                return validated

            logger.warning("Generated starter failed validation")
            return None

        except Exception as e:
            logger.error(f"Error generating conversation starter: {e}")
            return None

    async def generate_conversation_response(
        self,
        my_persona: Dict[str, Any],
        their_persona: Dict[str, Any],
        conversation_history: List[Dict[str, Any]],
        current_topic: str = None
    ) -> Optional[str]:
        """
        Generate a response in an ongoing conversation

        Args:
            my_persona: Persona of the responder
            their_persona: Persona of the other participant
            conversation_history: List of previous messages
            current_topic: Current conversation topic

        Returns:
            Response message text or None
        """
        # Format conversation history
        history_text = self._format_conversation_history(
            conversation_history,
            my_persona.get("generated_name", "Я")
        )

        # Extract topic if not provided
        if not current_topic and conversation_history:
            current_topic = "общение"

        prompt = CONVERSATION_RESPONSE_PROMPT.format(
            my_name=my_persona.get("generated_name", "Аноним"),
            my_age=my_persona.get("age", 25),
            my_occupation=my_persona.get("occupation", "не указано"),
            my_traits=", ".join(my_persona.get("personality_traits", ["дружелюбный"])),
            my_style=my_persona.get("communication_style", "дружелюбный"),
            my_interests=", ".join(my_persona.get("interests", ["общение"])),
            their_name=their_persona.get("generated_name", "Собеседник"),
            their_age=their_persona.get("age", 25),
            their_occupation=their_persona.get("occupation", "не указано"),
            their_interests=", ".join(their_persona.get("interests", ["общение"])),
            conversation_history=history_text,
            current_topic=current_topic
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=200,
                temperature=0.85,
                messages=[
                    {"role": "system", "content": "Ты генерируешь естественные ответы в Telegram чате. Отвечай ТОЛЬКО текстом сообщения."},
                    {"role": "user", "content": prompt}
                ]
            )

            text = response.choices[0].message.content.strip()
            validated = self._validate_message(text)

            if validated:
                logger.info(f"Generated response: {validated[:50]}...")
                return validated

            logger.warning("Generated response failed validation")
            return None

        except Exception as e:
            logger.error(f"Error generating conversation response: {e}")
            return None

    async def generate_closing_message(
        self,
        my_persona: Dict[str, Any],
        recent_messages: List[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Generate a message to naturally end a conversation

        Args:
            my_persona: Persona of the one closing
            recent_messages: Recent messages for context

        Returns:
            Closing message text or None
        """
        recent_text = ""
        if recent_messages:
            recent_text = self._format_conversation_history(
                recent_messages[-5:],
                my_persona.get("generated_name", "Я")
            )

        prompt = CONVERSATION_CLOSING_PROMPT.format(
            my_name=my_persona.get("generated_name", "Аноним"),
            my_style=my_persona.get("communication_style", "дружелюбный"),
            recent_messages=recent_text or "Диалог был на разные темы"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=100,
                temperature=0.8,
                messages=[
                    {"role": "system", "content": "Ты генерируешь завершающие сообщения для Telegram чата. Отвечай ТОЛЬКО текстом сообщения."},
                    {"role": "user", "content": prompt}
                ]
            )

            text = response.choices[0].message.content.strip()
            validated = self._validate_message(text, max_length=150)

            if validated:
                logger.info(f"Generated closing: {validated}")
                return validated

            # Fallback
            return "Ладно, пойду. Было приятно пообщаться!"

        except Exception as e:
            logger.error(f"Error generating closing message: {e}")
            return "Окей, мне пора. До связи!"

    async def generate_group_message(
        self,
        my_persona: Dict[str, Any],
        group_members: List[Dict[str, Any]],
        group_topic: str,
        group_type: str = "friends",
        recent_messages: List[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Generate a message for group chat.

        Args:
            my_persona: Persona of the sender
            group_members: Personas of other group members
            group_topic: Topic of the group
            group_type: Type of group (friends, thematic, work)
            recent_messages: Recent messages in the group

        Returns:
            Message text or None
        """
        # Format members info
        members_info = self._format_group_members(group_members)

        # Format recent messages
        if recent_messages:
            messages_text = self._format_group_messages(
                recent_messages,
                my_persona.get("generated_name", "Я")
            )
        else:
            messages_text = "Пока сообщений нет"

        # Choose prompt based on whether there are messages
        is_first_message = not recent_messages or len(recent_messages) == 0

        if is_first_message:
            prompt = GROUP_STARTER_PROMPT.format(
                my_name=my_persona.get("generated_name", "Аноним"),
                my_age=my_persona.get("age", 25),
                my_occupation=my_persona.get("occupation", "не указано"),
                my_style=my_persona.get("communication_style", "дружелюбный"),
                my_interests=", ".join(my_persona.get("interests", ["общение"])),
                group_type=self._translate_group_type(group_type),
                group_topic=group_topic,
                members_info=members_info
            )
        else:
            prompt = GROUP_MESSAGE_PROMPT.format(
                my_name=my_persona.get("generated_name", "Аноним"),
                my_age=my_persona.get("age", 25),
                my_occupation=my_persona.get("occupation", "не указано"),
                my_traits=", ".join(my_persona.get("personality_traits", ["дружелюбный"])),
                my_style=my_persona.get("communication_style", "дружелюбный"),
                my_interests=", ".join(my_persona.get("interests", ["общение"])),
                group_type=self._translate_group_type(group_type),
                group_topic=group_topic,
                members_info=members_info,
                recent_messages=messages_text
            )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=150,
                temperature=0.9,
                messages=[
                    {"role": "system", "content": "Ты генерируешь естественные сообщения для группового чата в Telegram. Отвечай ТОЛЬКО текстом сообщения."},
                    {"role": "user", "content": prompt}
                ]
            )

            text = response.choices[0].message.content.strip()
            validated = self._validate_message(text)

            if validated:
                logger.info(f"Generated group message: {validated[:50]}...")
                return validated

            logger.warning("Generated group message failed validation")
            return None

        except Exception as e:
            logger.error(f"Error generating group message: {e}")
            return None

    def _format_group_members(self, members: List[Dict[str, Any]]) -> str:
        """Format group members info for prompt"""
        if not members:
            return "Информация об участниках недоступна"

        lines = []
        for member in members[:5]:  # Limit to 5 members
            name = member.get("generated_name", "Участник")
            age = member.get("age", "?")
            occupation = member.get("occupation", "не указано")
            interests = ", ".join(member.get("interests", [])[:3])

            lines.append(f"- {name}, {age} лет, {occupation}. Интересы: {interests}")

        return "\n".join(lines) if lines else "Участники группы"

    def _format_group_messages(
        self,
        messages: List[Dict[str, Any]],
        my_name: str
    ) -> str:
        """Format group messages for prompt"""
        lines = []
        for msg in messages[-10:]:  # Last 10 messages
            sender_name = msg.get("sender_name", "Участник")
            # Mark my messages
            if msg.get("is_mine") or msg.get("sender_name") == my_name:
                sender_name = "Ты"
            text = msg.get("message_text", "")
            lines.append(f"{sender_name}: {text}")

        return "\n".join(lines) if lines else "Начало разговора"

    def _translate_group_type(self, group_type: str) -> str:
        """Translate group type to Russian"""
        translations = {
            "friends": "Дружеский чат",
            "thematic": "Тематический чат",
            "work": "Рабочий чат"
        }
        return translations.get(group_type, "Групповой чат")

    def _format_conversation_history(
        self,
        messages: List[Dict[str, Any]],
        my_name: str
    ) -> str:
        """Format conversation history for LLM prompt"""
        lines = []
        for msg in messages[-15:]:  # Last 15 messages
            sender_name = msg.get("sender_name", "Собеседник")
            # Mark my messages
            if msg.get("is_mine") or msg.get("sender_name") == my_name:
                sender_name = "Ты"
            text = msg.get("message_text", "")
            lines.append(f"{sender_name}: {text}")

        return "\n".join(lines) if lines else "Начало диалога"

    def _validate_message(
        self,
        text: str,
        min_length: int = 3,
        max_length: int = 500
    ) -> Optional[str]:
        """
        Validate and clean generated message

        Args:
            text: Raw message text
            min_length: Minimum allowed length
            max_length: Maximum allowed length

        Returns:
            Cleaned text or None if invalid
        """
        if not text:
            return None

        # Remove quotes
        text = text.strip().strip('"\'')

        # Remove markdown formatting that LLM might add
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)

        # Length checks
        if len(text) < min_length:
            return None
        if len(text) > max_length:
            text = text[:max_length]

        # Spam/promo patterns to reject
        spam_patterns = [
            'заработок', 'инвестиц', 'бесплатно получи',
            'акция', 'скидк', 'промокод', 'переходи по ссылке',
            'криптовалют', 'bitcoin', 'btc', 'usdt',
            'казино', 'ставк', 'выигрыш'
        ]

        text_lower = text.lower()
        for pattern in spam_patterns:
            if pattern in text_lower:
                logger.warning(f"Rejected message with spam pattern: {pattern}")
                return None

        return text


# Singleton instance
_conversation_agent: Optional[ConversationAgent] = None


def get_conversation_agent() -> ConversationAgent:
    """Get singleton instance of ConversationAgent"""
    global _conversation_agent
    if _conversation_agent is None:
        _conversation_agent = ConversationAgent()
    return _conversation_agent
