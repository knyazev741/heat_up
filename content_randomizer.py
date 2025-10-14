"""
ContentRandomizer - генерация вариаций сообщений для избежания детекции
"""

import logging
from typing import List, Dict, Any
from openai import OpenAI
from config import settings
import json

logger = logging.getLogger(__name__)


class ContentRandomizer:
    """
    Рандомизация контента для избежания детекции нейросетями Telegram
    
    Генерирует уникальные вариации сообщений с сохранением смысла
    """
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o-mini"
    
    async def generate_message_variations(
        self,
        base_message: str,
        persona: Dict[str, Any],
        count: int = 5
    ) -> List[str]:
        """
        Генерирует N вариаций сообщения в стиле персоны
        
        Args:
            base_message: Базовое сообщение
            persona: Данные персоны
            count: Количество вариаций
            
        Returns:
            Список уникальных вариаций сообщения
        """
        
        if not persona:
            # Если персоны нет, генерируем простые вариации
            return await self._generate_simple_variations(base_message, count)
        
        logger.info(f"Generating {count} message variations for: '{base_message[:50]}...'")
        
        communication_style = persona.get("communication_style", "casual")
        personality_traits = ", ".join(persona.get("personality_traits", []))
        
        prompt = f"""Сгенерируй {count} РАЗНЫХ вариаций следующего сообщения:

Исходное сообщение: "{base_message}"

Требования к вариациям:
- Сохрани основной смысл
- Каждая вариация должна быть УНИКАЛЬНОЙ
- Используй разные слова, синонимы, фразы
- Стиль общения: {communication_style}
- Характер: {personality_traits}
- Разная длина (некоторые короче, некоторые длиннее)
- {"Используй эмодзи" if communication_style == "emoji_heavy" else "Минимум эмодзи или без них"}

Примеры хорошей вариации:
Исходное: "Спасибо за информацию!"
Вариации:
1. "Благодарю, очень полезно 👍"
2. "Спасибо, это то что нужно"
3. "Ок, принял информацию"
4. "Thanks!"
5. "Отлично, спасибо большое"

Формат ответа - JSON массив строк:
["вариация 1", "вариация 2", ...]

Только JSON, без дополнительного текста!"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=1.2,  # Очень высокая температура для максимального разнообразия
                max_tokens=1024,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты эксперт по перефразированию и созданию уникального контента. Отвечай только в формате JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
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
            
            variations = json.loads(json_str)
            
            if isinstance(variations, list) and len(variations) > 0:
                logger.info(f"Generated {len(variations)} variations successfully")
                return variations[:count]
            else:
                logger.warning("Invalid variations format, using fallback")
                return await self._generate_simple_variations(base_message, count)
        
        except Exception as e:
            logger.error(f"Error generating variations: {e}")
            return await self._generate_simple_variations(base_message, count)
    
    async def _generate_simple_variations(self, base_message: str, count: int) -> List[str]:
        """Простые вариации без LLM"""
        
        variations = [base_message]
        
        # Простые трансформации
        templates = [
            base_message,
            base_message + " 👍",
            base_message.lower(),
            base_message.capitalize(),
            f"✅ {base_message}"
        ]
        
        for template in templates[:count]:
            if template not in variations:
                variations.append(template)
        
        return variations[:count]
    
    async def generate_reply_for_context(
        self,
        persona: Dict[str, Any],
        chat_context: str,
        message_to_reply: str
    ) -> str:
        """
        Генерирует естественный ответ на сообщение в контексте чата
        
        Args:
            persona: Данные персоны
            chat_context: Контекст чата (последние сообщения)
            message_to_reply: Сообщение, на которое отвечаем
            
        Returns:
            Сгенерированный ответ
        """
        
        if not persona:
            return "Interesting, thanks!"
        
        logger.info(f"Generating reply for message: '{message_to_reply[:50]}...'")
        
        prompt = f"""Ты - пользователь Telegram со следующей личностью:

Имя: {persona.get('generated_name')}
Характер: {', '.join(persona.get('personality_traits', []))}
Интересы: {', '.join(persona.get('interests', []))}
Стиль общения: {persona.get('communication_style')}

Контекст чата (последние сообщения):
{chat_context}

Сообщение, на которое нужно ответить:
"{message_to_reply}"

Напиши КОРОТКИЙ (1-2 предложения), ЕСТЕСТВЕННЫЙ ответ в своем стиле.

ВАЖНО:
- Ответ должен быть РЕЛЕВАНТНЫМ сообщению
- Как будто пишет реальный человек
- НЕ спамный, НЕ рекламный
- Соответствует твоему характеру и стилю

Формат ответа - просто текст сообщения, без кавычек и JSON!"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=0.9,
                max_tokens=256,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты помогаешь генерировать естественные ответы в стиле персоны."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            reply = response.choices[0].message.content.strip()
            
            # Remove quotes if present
            reply = reply.strip('"\'')
            
            logger.info(f"Generated reply: '{reply}'")
            return reply
        
        except Exception as e:
            logger.error(f"Error generating reply: {e}")
            return "Thanks for sharing!"

