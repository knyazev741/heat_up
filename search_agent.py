"""
SearchAgent - поиск релевантных Telegram-чатов для персоны
"""

import json
import logging
from typing import Dict, Any, List
from openai import OpenAI
from config import settings
from channels_catalog import get_all_channels, get_channels_by_keywords

logger = logging.getLogger(__name__)


class SearchAgent:
    """
    Агент поиска релевантных Telegram-чатов для персоны
    
    1. Анализирует личность (интересы, город, профессия)
    2. Находит подходящие каналы из каталога
    3. LLM ранжирует каналы по релевантности
    4. Возвращает персональный пул для этого аккаунта
    """
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o-mini"
        self.all_channels = get_all_channels()  # Загружаем все каналы из каталога
    
    async def find_relevant_chats(
        self,
        persona: Dict[str, Any],
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Находит релевантные чаты для персоны из каталога
        
        Args:
            persona: Словарь с данными персоны
            limit: Максимальное количество чатов для возврата
            
        Returns:
            Список чатов с оценкой релевантности
        """
        logger.info(f"Finding relevant chats for persona: {persona.get('generated_name')}")
        
        # 1. Собираем ключевые слова из личности
        keywords = []
        keywords.extend(persona.get("interests", []))
        if persona.get("occupation"):
            keywords.append(persona.get("occupation"))
        if persona.get("city"):
            keywords.append(persona.get("city"))
        
        logger.info(f"Search keywords: {keywords}")
        
        # 2. Находим подходящие каналы по ключевым словам
        matching_channels = get_channels_by_keywords(keywords)
        
        # 3. Добавляем общие популярные каналы
        all_candidates = matching_channels + self.all_channels
        
        # 4. Убираем дубликаты
        unique_channels = {}
        for ch in all_candidates:
            username = ch.get("username", "").lower()
            if username and username not in unique_channels:
                unique_channels[username] = ch
        
        channels_list = list(unique_channels.values())
        logger.info(f"Found {len(channels_list)} candidate channels from catalog")
        
        if not channels_list:
            logger.warning("No channels in catalog, returning defaults")
            return self._get_default_channels()
        
        # 5. Конвертируем в формат для БД
        formatted_channels = []
        for ch in channels_list:
            formatted_channels.append({
                "chat_username": ch.get("username"),
                "chat_title": ch.get("title"),
                "chat_description": ch.get("description"),
                "chat_type": "channel",
                "member_count": None,
                "source_query": f"catalog:{ch.get('category', 'general')}"
            })
        
        # 6. LLM ранжирует по релевантности для персоны
        ranked_chats = await self._rank_chats(formatted_channels, persona)
        
        # 7. Сортируем и возвращаем топ
        ranked_chats.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        
        return ranked_chats[:limit]
    
    
    async def _rank_chats(
        self,
        chats: List[Dict[str, Any]],
        persona: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        LLM оценивает релевантность чатов для персоны
        
        Args:
            chats: Список чатов из пула
            persona: Данные персоны
            
        Returns:
            Список чатов с добавленными полями relevance_score и relevance_reason
        """
        
        if not chats:
            return []
        
        # Ограничиваем количество для LLM (чтобы не превысить токены)
        chats_to_rank = chats[:30]
        
        # Формируем описание чатов для LLM
        chats_description = []
        for idx, chat in enumerate(chats_to_rank):
            username = chat.get('chat_username', 'unknown')
            desc = f"{idx}. {username}"
            description = chat.get('chat_description', '')
            if description:
                desc += f" - {description[:100]}"
            source_query = chat.get('source_query', '')
            if source_query:
                desc += f" [Найден по запросу: '{source_query}']"
            chats_description.append(desc)
        
        chats_text = "\n".join(chats_description)
        
        prompt = f"""У нас есть пользователь:
{persona.get('full_description', '')}

Интересы: {', '.join(persona.get('interests', []))}
Профессия: {persona.get('occupation')}
Город: {persona.get('city')}

Список найденных Telegram-каналов:
{chats_text}

Оцени релевантность КАЖДОГО канала для этого пользователя по шкале от 0 до 1:
- 1.0 = идеально подходит (по интересам, городу, профессии)
- 0.7-0.9 = хорошо подходит
- 0.4-0.6 = средне
- 0.1-0.3 = слабо подходит
- 0.0 = не подходит

ВАЖНО:
- Приоритет ГРУППАМ для общения (а не только каналам для чтения)
- Локальные чаты города - высокий приоритет
- Тематические чаты по интересам - высокий приоритет
- Профессиональные сообщества - высокий приоритет

Формат ответа - JSON массив объектов:
[
  {{
    "index": 0,
    "relevance_score": 0.85,
    "relevance_reason": "Канал о технологиях, соответствует интересам пользователя"
  }},
  ...
]

Только JSON, без дополнительного текста!"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=0.3,  # Низкая температура для более последовательной оценки
                max_tokens=2048,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты эксперт по оценке релевантности контента. Отвечай только в формате JSON."
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
            
            rankings = json.loads(json_str)
            
            # Применяем оценки к чатам
            ranked_chats = []
            for ranking in rankings:
                idx = ranking.get("index")
                if idx is not None and 0 <= idx < len(chats_to_rank):
                    chat = chats_to_rank[idx].copy()
                    chat["relevance_score"] = ranking.get("relevance_score", 0.5)
                    chat["relevance_reason"] = ranking.get("relevance_reason", "")
                    # Поля уже нормализованы в _extract_telegram_links
                    ranked_chats.append(chat)
            
            logger.info(f"Successfully ranked {len(ranked_chats)} chats")
            return ranked_chats
            
        except Exception as e:
            logger.error(f"Error ranking chats: {e}")
            # Возвращаем чаты с дефолтной оценкой
            return self._apply_default_ranking(chats_to_rank)
    
    def _apply_default_ranking(self, chats: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Применить дефолтный ранжинг если LLM failed"""
        
        ranked = []
        for chat in chats:
            chat_copy = chat.copy()
            # Простая оценка - все одинаковые
            chat_copy["relevance_score"] = 0.5
            chat_copy["relevance_reason"] = "Default ranking (LLM unavailable)"
            # Поля уже нормализованы в _extract_telegram_links
            ranked.append(chat_copy)
        
        return ranked
    
    def _get_default_channels(self) -> List[Dict[str, Any]]:
        """Возвращает дефолтные каналы как fallback"""
        
        default = [
            {
                "chat_username": "@telegram",
                "chat_title": "Telegram News",
                "chat_description": "Official Telegram channel",
                "chat_type": "channel",
                "member_count": None,
                "relevance_score": 0.8,
                "relevance_reason": "Official channel, good for new users"
            },
            {
                "chat_username": "@durov",
                "chat_title": "Pavel Durov",
                "chat_description": "Founder's channel",
                "chat_type": "channel",
                "member_count": None,
                "relevance_score": 0.7,
                "relevance_reason": "Telegram founder"
            }
        ]
        
        return default

