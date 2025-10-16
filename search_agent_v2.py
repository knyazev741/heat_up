"""
SearchAgent V2 - Генерация вероятных Telegram-чатов через LLM
Веб-поиск НЕ РАБОТАЕТ (DuckDuckGo не индексирует t.me)
"""

import json
import logging
from typing import Dict, Any, List
from openai import OpenAI
from config import settings

logger = logging.getLogger(__name__)


class SearchAgent:
    """
    Агент генерации вероятных Telegram-чатов для персоны через LLM
    
    1. Анализирует личность (интересы, город, профессия)
    2. LLM генерирует вероятные username групп/каналов
    3. LLM ранжирует по релевантности
    4. Возвращает персональный пул для аккаунта
    """
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o"
    
    async def find_relevant_chats(
        self,
        persona: Dict[str, Any],
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Генерирует вероятные Telegram-чаты для персоны
        
        Args:
            persona: Словарь с данными персоны
            limit: Максимальное количество чатов
            
        Returns:
            Список чатов с метаданными
        """
        logger.info(f"Generating probable Telegram chats for: {persona.get('generated_name')}")
        
        # Генерируем вероятные username через LLM
        chats = await self._generate_probable_chats(persona, limit)
        
        logger.info(f"Generated {len(chats)} probable chats")
        return chats
    
    async def _generate_probable_chats(
        self,
        persona: Dict[str, Any],
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        LLM генерирует вероятные username Telegram-групп
        """
        
        city = persona.get('city', '')
        country = persona.get('country', '')
        interests = persona.get('interests', [])
        occupation = persona.get('occupation', '')
        
        prompt = f"""Ты эксперт по Telegram. Сгенерируй список ВЕРОЯТНЫХ username публичных Telegram-групп и каналов для этого человека:

Город: {city}, {country}
Интересы: {', '.join(interests)}
Профессия: {occupation}

ПРАВИЛА генерации username:
1. Начинаются с @ (например @moscowchat, @python_ru)
2. Только латиница, цифры, подчеркивания
3. Обычно короткие (5-20 символов)
4. Логичные паттерны:
   - Город: @moscowchat, @spb_chat, @kazan_live
   - Тема: @python_ru, @javascript_chat, @cooking_ru
   - Профессия: @doctors_ru, @teachers_chat
5. Добавляй _ru, _rus, _chat, _group для русских чатов
6. Генерируй РАЗНЫЕ типы:
   - 50% ГРУППЫ (@*_chat, @*_group) - ДЛЯ ОБЩЕНИЯ
   - 30% каналы города (@city_news, @city_live)
   - 20% тематические каналы

ПРИОРИТЕТЫ:
1. Группы ГОРОДА (очень высокий приоритет) - @{city.lower().replace(' ', '').replace('-', '')}_chat
2. Тематические группы по интересам
3. Профессиональные сообщества
4. Общие каналы

Сгенерируй {limit} ВЕРОЯТНЫХ username. Они могут НЕ существовать, но должны выглядеть реалистично.

Формат - JSON массив:
[
  {{
    "username": "@moscowchat",
    "title": "Москва | Чат",
    "description": "Общение жителей Москвы",
    "chat_type": "group",
    "relevance_score": 0.95,
    "relevance_reason": "Группа города пользователя, максимальная релевантность"
  }},
  ...
]

chat_type: "group" (можно писать) или "channel" (только чтение)

ТОЛЬКО JSON!"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=0.8,  # Достаточно креативности для разнообразия
                max_tokens=3000,
                messages=[
                    {"role": "system", "content": "Ты эксперт по Telegram. Генеруешь вероятные username групп и каналов. Отвечай только JSON."},
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
            
            chats = json.loads(json_str)
            
            # Конвертируем в формат для БД
            formatted_chats = []
            for chat in chats:
                formatted_chats.append({
                    "chat_username": chat.get("username", ""),
                    "chat_title": chat.get("title", ""),
                    "chat_description": chat.get("description", ""),
                    "chat_type": chat.get("chat_type", "unknown"),
                    "member_count": None,
                    "relevance_score": chat.get("relevance_score", 0.5),
                    "relevance_reason": chat.get("relevance_reason", "")
                })
            
            logger.info(f"LLM generated {len(formatted_chats)} chats")
            
            # Логируем примеры
            for i, chat in enumerate(formatted_chats[:5]):
                logger.info(f"  {i+1}. {chat['chat_username']} ({chat['chat_type']}, score: {chat['relevance_score']:.2f})")
            
            return formatted_chats
            
        except Exception as e:
            logger.error(f"Error generating chats: {e}")
            return self._get_fallback_chats(persona)
    
    def _get_fallback_chats(self, persona: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fallback если LLM failed"""
        
        city = persona.get('city', 'Moscow')
        city_normalized = city.lower().replace(' ', '').replace('-', '')[:15]
        
        return [
            {
                "chat_username": f"@{city_normalized}_chat",
                "chat_title": f"{city} | Чат",
                "chat_description": f"Общение жителей {city}",
                "chat_type": "group",
                "member_count": None,
                "relevance_score": 0.9,
                "relevance_reason": "Группа города"
            },
            {
                "chat_username": f"@{city_normalized}_news",
                "chat_title": f"{city} | Новости",
                "chat_description": f"Новости {city}",
                "chat_type": "channel",
                "member_count": None,
                "relevance_score": 0.7,
                "relevance_reason": "Канал города"
            }
        ]

