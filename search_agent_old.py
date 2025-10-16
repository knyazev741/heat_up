"""
SearchAgent - РЕАЛЬНЫЙ поиск Telegram-чатов и каналов через веб-поиск
"""

import json
import logging
import re
from typing import Dict, Any, List
from openai import OpenAI
from config import settings

logger = logging.getLogger(__name__)


class SearchAgent:
    """
    Агент поиска РЕАЛЬНЫХ Telegram-чатов для персоны
    
    1. Генерирует поисковые запросы на основе интересов персоны
    2. Делает РЕАЛЬНЫЙ веб-поиск (DuckDuckGo)
    3. Парсит результаты и извлекает Telegram-ссылки
    4. LLM ранжирует найденные чаты по релевантности
    5. Возвращает персональный пул для этого аккаунта
    """
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o"
        # Попробуем импортировать библиотеку для поиска
        try:
            from duckduckgo_search import DDGS
            self.ddgs = DDGS()
            self.search_available = True
            logger.info("DuckDuckGo search initialized successfully")
        except ImportError:
            logger.warning("duckduckgo_search not installed, search will be limited")
            self.ddgs = None
            self.search_available = False
    
    async def find_relevant_chats(
        self,
        persona: Dict[str, Any],
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Находит РЕАЛЬНЫЕ Telegram-чаты для персоны через веб-поиск
        
        Args:
            persona: Словарь с данными персоны
            limit: Максимальное количество чатов для возврата
            
        Returns:
            Список чатов с оценкой релевантности
        """
        logger.info(f"Finding REAL Telegram chats for: {persona.get('generated_name')}")
        
        # 1. Генерируем поисковые запросы
        search_queries = self._generate_search_queries(persona)
        logger.info(f"Generated {len(search_queries)} search queries")
        
        # 2. Выполняем поиск для каждого запроса
        all_results = []
        for query in search_queries[:5]:  # Ограничиваем до 5 запросов
            logger.info(f"Searching: {query}")
            results = await self._web_search(query)
            all_results.extend(results)
        
        logger.info(f"Found {len(all_results)} search results total")
        
        # 3. Извлекаем Telegram-ссылки из результатов
        telegram_links = self._extract_telegram_links(all_results)
        logger.info(f"Extracted {len(telegram_links)} Telegram links")
        
        if not telegram_links:
            logger.warning("No Telegram links found, returning empty list")
            return []
        
        # 4. Конвертируем в формат для БД
        formatted_chats = []
        for link in telegram_links:
            formatted_chats.append({
                "chat_username": link.get("username"),
                "chat_title": link.get("title", link.get("username")),
                "chat_description": link.get("description", ""),
                "chat_type": link.get("type", "unknown"),
                "member_count": None,
                "source_query": link.get("source_query", "")
            })
        
        # 5. LLM ранжирует по релевантности
        ranked_chats = await self._rank_chats(formatted_chats, persona)
        
        # 6. Сортируем и возвращаем топ
        ranked_chats.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        
        logger.info(f"Returning top {min(limit, len(ranked_chats))} chats")
        return ranked_chats[:limit]
    
    def _generate_search_queries(self, persona: Dict[str, Any]) -> List[str]:
        """
        Генерирует поисковые запросы для поиска Telegram-чатов
        
        Args:
            persona: Данные персоны
            
        Returns:
            Список поисковых запросов
        """
        queries = []
        
        interests = persona.get("interests", [])
        city = persona.get("city", "")
        occupation = persona.get("occupation", "")
        
        # Запросы по городу
        if city:
            queries.append(f"telegram группа чат {city}")
            queries.append(f"{city} telegram группа")
            queries.append(f"telegram {city} сообщество")
        
        # Запросы по интересам (первые 3)
        for interest in interests[:3]:
            queries.append(f"telegram группа {interest}")
            queries.append(f"{interest} telegram канал")
            queries.append(f"telegram чат {interest} россия")
        
        # Запрос по профессии
        if occupation:
            queries.append(f"telegram {occupation} сообщество")
            queries.append(f"{occupation} telegram группа")
        
        return queries
    
    async def _web_search(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Выполняет веб-поиск через DuckDuckGo
        
        Args:
            query: Поисковый запрос
            max_results: Максимум результатов
            
        Returns:
            Список результатов поиска
        """
        if not self.search_available or not self.ddgs:
            logger.warning("Search not available, returning empty results")
            return []
        
        try:
            results = []
            # Используем text search от DuckDuckGo
            search_results = self.ddgs.text(query, max_results=max_results)
            
            for result in search_results:
                results.append({
                    "title": result.get("title", ""),
                    "url": result.get("href", ""),
                    "description": result.get("body", ""),
                    "source_query": query
                })
            
            logger.info(f"Found {len(results)} results for '{query}'")
            return results
            
        except Exception as e:
            logger.error(f"Error during web search for '{query}': {e}")
            return []
    
    def _extract_telegram_links(self, search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Извлекает Telegram-ссылки из результатов поиска
        
        Args:
            search_results: Результаты веб-поиска
            
        Returns:
            Список Telegram-чатов с метаданными
        """
        telegram_chats = []
        seen_usernames = set()
        
        # Регулярки для поиска Telegram-ссылок
        patterns = [
            r't\.me/([a-zA-Z0-9_]+)',  # t.me/username
            r'telegram\.me/([a-zA-Z0-9_]+)',  # telegram.me/username
            r'@([a-zA-Z0-9_]+)',  # @username (осторожно, может быть много шума)
        ]
        
        for result in search_results:
            url = result.get("url", "")
            title = result.get("title", "")
            description = result.get("description", "")
            text = f"{url} {title} {description}"
            
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    username = match.lower()
                    
                    # Фильтрация: пропускаем слишком короткие и общие
                    if len(username) < 4:
                        continue
                    if username in ['telegram', 'bot', 'channel', 'group']:
                        continue
                    
                    # Добавляем только уникальные
                    if username not in seen_usernames:
                        seen_usernames.add(username)
                        
                        # Определяем тип по ключевым словам
                        chat_type = "unknown"
                        if "группа" in title.lower() or "group" in title.lower() or "чат" in title.lower():
                            chat_type = "group"
                        elif "канал" in title.lower() or "channel" in title.lower():
                            chat_type = "channel"
                        
                        telegram_chats.append({
                            "username": f"@{username}" if not username.startswith("@") else username,
                            "title": title,
                            "description": description,
                            "type": chat_type,
                            "source_query": result.get("source_query", ""),
                            "source_url": url
                        })
        
        return telegram_chats
    
    async def _rank_chats(
        self,
        chats: List[Dict[str, Any]],
        persona: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        LLM оценивает релевантность найденных чатов для персоны
        
        Args:
            chats: Список найденных чатов
            persona: Данные персоны
            
        Returns:
            Список чатов с relevance_score и relevance_reason
        """
        if not chats:
            return []
        
        # Ограничиваем для LLM
        chats_to_rank = chats[:30]
        
        # Формируем описание
        chats_description = []
        for idx, chat in enumerate(chats_to_rank):
            username = chat.get('chat_username', 'unknown')
            chat_type = chat.get('chat_type', 'unknown')
            type_marker = "💬" if "group" in chat_type else "📢" if "channel" in chat_type else "❓"
            
            desc = f"{idx}. {type_marker} {username}"
            
            title = chat.get('chat_title', '')
            if title:
                desc += f" - {title[:80]}"
            
            description = chat.get('chat_description', '')
            if description:
                desc += f" | {description[:100]}"
            
            source_query = chat.get('source_query', '')
            if source_query:
                desc += f" [Запрос: {source_query}]"
            
            chats_description.append(desc)
        
        chats_text = "\n".join(chats_description)
        
        prompt = f"""Пользователь:
{persona.get('full_description', '')}

Интересы: {', '.join(persona.get('interests', []))}
Профессия: {persona.get('occupation')}
Город: {persona.get('city')}, {persona.get('country')}

Найденные РЕАЛЬНЫЕ Telegram-чаты (через поиск):
{chats_text}

Оцени релевантность КАЖДОГО чата по шкале 0-1:
- 1.0 = идеально подходит
- 0.8-0.9 = отлично
- 0.6-0.7 = хорошо
- 0.4-0.5 = средне
- 0.2-0.3 = слабо
- 0.0-0.1 = не подходит

ПРИОРИТЕТЫ:
1. 💬 Группы для общения > 📢 Каналы для чтения
2. Чаты ГОРОДА - максимальный приоритет (0.9+)
3. Тематические группы по ИНТЕРЕСАМ (0.7+)
4. Профессиональные сообщества (0.7+)

Формат - JSON массив:
[
  {{
    "index": 0,
    "relevance_score": 0.85,
    "relevance_reason": "Группа города пользователя, высокая релевантность"
  }},
  ...
]

ТОЛЬКО JSON!"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=0.3,
                max_tokens=2048,
                messages=[
                    {"role": "system", "content": "Эксперт по оценке релевантности. Отвечай только JSON."},
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
            
            # Применяем оценки
            ranked_chats = []
            for ranking in rankings:
                idx = ranking.get("index")
                if idx is not None and 0 <= idx < len(chats_to_rank):
                    chat = chats_to_rank[idx].copy()
                    chat["relevance_score"] = ranking.get("relevance_score", 0.5)
                    chat["relevance_reason"] = ranking.get("relevance_reason", "")
                    ranked_chats.append(chat)
            
            logger.info(f"Successfully ranked {len(ranked_chats)} chats")
            return ranked_chats
            
        except Exception as e:
            logger.error(f"Error ranking chats: {e}")
            # Возвращаем с дефолтным score
            for chat in chats_to_rank:
                chat["relevance_score"] = 0.5
                chat["relevance_reason"] = "Default ranking (LLM error)"
            return chats_to_rank
