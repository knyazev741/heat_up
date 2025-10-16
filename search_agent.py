"""
SearchAgent - REAL web search для Telegram каналов через DuckDuckGo
"""

import re
import logging
from typing import Dict, Any, List
from ddgs import DDGS
from openai import OpenAI
from config import settings
import json

logger = logging.getLogger(__name__)


class SearchAgent:
    """
    Агент поиска РЕАЛЬНЫХ Telegram-чатов через DuckDuckGo
    
    1. Генерирует разные поисковые запросы (город + интересы)
    2. Ищет в DuckDuckGo
    3. Извлекает Telegram-ссылки из результатов
    4. LLM оценивает релевантность каналов
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
        Ищет РЕАЛЬНЫЕ Telegram-чаты через DuckDuckGo
        
        Args:
            persona: Словарь с данными персоны
            limit: Максимальное количество чатов
            
        Returns:
            Список чатов с метаданными
        """
        logger.info(f"🔍 Searching REAL Telegram chats for: {persona.get('generated_name')}")
        
        # Генерируем поисковые запросы
        queries = self._generate_search_queries(persona)
        logger.info(f"Generated {len(queries)} search queries")
        
        # Ищем в DuckDuckGo
        all_channels = {}  # {username: {title, description}}
        
        with DDGS() as ddgs:
            for q in queries:
                logger.info(f"Searching: {q}")
                try:
                    results = list(ddgs.text(q, max_results=10))
                    logger.info(f"  → Got {len(results)} search results")
                    
                    # Извлекаем каналы
                    channels = self._extract_channels_from_results(results)
                    logger.info(f"  → Extracted {len(channels)} channels")
                    
                    for ch in channels:
                        username = ch['username']
                        if username not in all_channels:
                            all_channels[username] = ch
                    
                except Exception as e:
                    logger.error(f"Search error for '{q}': {e}")
                    continue
        
        logger.info(f"Found {len(all_channels)} UNIQUE channels total")
        
        if not all_channels:
            logger.warning("No channels found via web search!")
            return []
        
        # LLM ранжирует по релевантности
        ranked_chats = await self._rank_chats_with_llm(persona, list(all_channels.values()))
        
        return ranked_chats[:limit]
    
    def _generate_search_queries(self, persona: Dict[str, Any]) -> List[str]:
        """Генерирует разные форматы поисковых запросов"""
        
        city = persona.get('city', 'Москва')
        interests = persona.get('interests', [])
        occupation = persona.get('occupation', '')
        
        queries = []
        
        # ГРУППЫ ГОРОДА (высший приоритет)
        queries.extend([
            f"{city} telegram group chat",
            f"t.me {city} жители",
            f"telegram чат {city} общение",
            f"{city} telegram группа",
        ])
        
        # ТЕМАТИЧЕСКИЕ ГРУППЫ по интересам
        for interest in interests[:3]:  # Топ-3 интереса
            queries.extend([
                f"{city} {interest} telegram",
                f"t.me {interest} {city}",
                f"telegram группа {interest}",
            ])
        
        # ПРОФЕССИОНАЛЬНЫЕ группы
        if occupation:
            queries.append(f"telegram {occupation} {city}")
        
        # НОВОСТИ ГОРОДА
        queries.append(f"telegram канал {city} новости")
        
        return queries[:15]  # Макс 15 запросов
    
    def _extract_channels_from_results(self, results: List[Dict]) -> List[Dict[str, Any]]:
        """Извлекает Telegram-каналы из результатов поиска"""
        
        channels = {}
        
        for r in results:
            href = r.get('href', '')
            title = r.get('title', '')
            body = r.get('body', '')
            
            full_text = f"{href} {title} {body}"
            
            # Извлекаем t.me/xxx или telegram.me/xxx
            t_me_links = re.findall(r'(?:t\.me|telegram\.me)/([a-zA-Z0-9_]+)', full_text)
            for username in t_me_links:
                if len(username) >= 5 and username not in channels:
                    channels[username] = {
                        'username': f"@{username}",
                        'title': title[:100] if title else username,
                        'description': body[:200] if body else '',
                        'source_url': href
                    }
            
            # Извлекаем @xxx упоминания
            mentions = re.findall(r'@([a-zA-Z][a-zA-Z0-9_]{4,31})', body)
            for username in mentions:
                # Фильтруем не-telegram username
                if username.lower() in ['gmail', 'mail', 'yandex', 'yahoo', 'outlook']:
                    continue
                    
                if username not in channels:
                    channels[username] = {
                        'username': f"@{username}",
                        'title': title[:100] if title else username,
                        'description': body[:200] if body else '',
                        'source_url': href
                    }
        
        return list(channels.values())
    
    async def _rank_chats_with_llm(
        self,
        persona: Dict[str, Any],
        channels: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """LLM оценивает релевантность каналов для персоны"""
        
        if not channels:
            return []
        
        # Ограничиваем для LLM (слишком много = дорого)
        channels_for_llm = channels[:30]
        
        # Формируем данные для LLM
        channels_list = "\n".join([
            f"{i+1}. {ch['username']} - {ch['title']} ({ch.get('description', '')[:80]})"
            for i, ch in enumerate(channels_for_llm)
        ])
        
        prompt = f"""Ты эксперт по Telegram. Оцени релевантность каналов/групп для этого пользователя:

Пользователь:
- Город: {persona.get('city')}
- Интересы: {', '.join(persona.get('interests', []))}
- Профессия: {persona.get('occupation')}
- Возраст: {persona.get('age')}

Найденные каналы:
{channels_list}

Оцени КАЖДЫЙ канал по релевантности (0.0-1.0):
- 1.0 = ИДЕАЛЬНО подходит (группа города, точное попадание по интересам)
- 0.8 = Отлично (тематическая группа по интересам)
- 0.5 = Средне (может быть интересно)
- 0.3 = Слабо (косвенная связь)
- 0.0 = Не подходит

ПРИОРИТЕТЫ:
1. Группы/чаты ГОРОДА для общения (group/supergroup) - ВЫСШИЙ ПРИОРИТЕТ!
2. Тематические группы по ИНТЕРЕСАМ в городе
3. Профессиональные сообщества
4. Общие каналы города (новости)

Определи тип (group/channel/supergroup) - группы лучше чем каналы!

Формат ответа - JSON массив:
[
  {{
    "username": "@example",
    "relevance_score": 0.9,
    "chat_type": "group",
    "reason": "Группа города для общения"
  }},
  ...
]

ТОЛЬКО JSON!"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=0.3,
                max_tokens=3000,
                messages=[
                    {"role": "system", "content": "Ты эксперт по Telegram. Отвечай только JSON."},
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
            
            rankings = json.loads(json_str)
            
            # Объединяем с оригинальными данными
            username_to_channel = {ch['username']: ch for ch in channels_for_llm}
            
            ranked_chats = []
            for rank in rankings:
                username = rank.get('username', '')
                if username in username_to_channel:
                    original = username_to_channel[username]
                    ranked_chats.append({
                        "chat_username": username,
                        "chat_title": original.get('title', ''),
                        "chat_description": original.get('description', ''),
                        "chat_type": rank.get('chat_type', 'unknown'),
                        "member_count": None,
                        "relevance_score": rank.get('relevance_score', 0.5),
                        "relevance_reason": rank.get('reason', '')
                    })
            
            logger.info(f"LLM ranked {len(ranked_chats)} chats")
            
            # Логируем топ-5
            for i, chat in enumerate(sorted(ranked_chats, key=lambda x: x['relevance_score'], reverse=True)[:5]):
                logger.info(f"  {i+1}. {chat['chat_username']} ({chat['chat_type']}, score: {chat['relevance_score']:.2f})")
            
            return ranked_chats
            
        except Exception as e:
            logger.error(f"Error ranking chats: {e}")
            
            # Fallback - просто возвращаем каналы как есть
            return [{
                "chat_username": ch['username'],
                "chat_title": ch.get('title', ''),
                "chat_description": ch.get('description', ''),
                "chat_type": "unknown",
                "member_count": None,
                "relevance_score": 0.5,
                "relevance_reason": "Found via search"
            } for ch in channels_for_llm]
