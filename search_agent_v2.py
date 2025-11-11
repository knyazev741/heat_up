"""
SearchAgent V2 - с реальным переходом на сайты и извлечением ссылок
"""

import re
import logging
import asyncio
from typing import Dict, Any, List, Set
from duckduckgo_search import DDGS
from openai import OpenAI
from config import settings
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)


class SearchAgentV2:
    """
    Агент поиска с реальным web scraping
    
    1. Генерирует поисковые запросы (город + интересы)
    2. Ищет в DuckDuckGo
    3. ПЕРЕХОДИТ НА САЙТЫ и скрейпит HTML
    4. Извлекает Telegram-ссылки со страниц
    5. LLM оценивает релевантность каналов
    """
    
    def __init__(self):
        # Using DeepSeek API (OpenAI-compatible)
        self.client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com"
        )
        self.model = "deepseek-chat"
        
        # HTTP клиент для скрейпинга
        self.http_client = httpx.AsyncClient(
            timeout=10.0,  # 10 секунд на запрос
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            }
        )
        
        # Черный список доменов (не скрейпим)
        self.blacklisted_domains = {
            'instagram.com', 'facebook.com', 'twitter.com', 'x.com',
            'youtube.com', 'tiktok.com', 'linkedin.com', 'reddit.com',
            'pinterest.com', 'amazon.com', 'ebay.com'
        }
        
        # Черный список username
        self.blacklisted_usernames = {
            'gmail', 'mail', 'yandex', 'yahoo', 'outlook', 'hotmail', 'icloud',
            'protonmail', 'aol', 'zoho', 'mailru', 'rambler',
            'instagram', 'facebook', 'twitter', 'tiktok', 'youtube', 'linkedin',
            'whatsapp', 'viber', 'skype', 'discord', 'snapchat',
            'pinterest', 'reddit', 'tumblr', 'flickr', 'vimeo',
            'amazon', 'ebay', 'aliexpress', 'spotify', 'netflix',
            'google', 'microsoft', 'apple', 'samsung', 'huawei',
            'twitch', 'steam', 'playstation', 'xbox', 'nintendo',
            'badoo', 'tinder', 'bumble', 'hinge', 'okcupid',
            'magenta', 'telekom', 'vodafone', 'orange', 't-mobile',
            'katyperry', 'justinbieber', 'arianagrande', 'selenagomez'
        }
    
    async def find_relevant_chats(
        self,
        persona: Dict[str, Any],
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Ищет РЕАЛЬНЫЕ Telegram-чаты через DuckDuckGo + web scraping
        
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
        
        # Ищем в DuckDuckGo (получаем URLs)
        urls_to_scrape = await self._search_duckduckgo(queries)
        logger.info(f"Got {len(urls_to_scrape)} URLs to scrape")
        
        # Скрейпим сайты
        all_channels = await self._scrape_websites(urls_to_scrape)
        logger.info(f"Found {len(all_channels)} UNIQUE channels after scraping")
        
        if not all_channels:
            logger.warning("No channels found via web scraping!")
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
    
    async def _search_duckduckgo(self, queries: List[str]) -> List[Dict[str, Any]]:
        """Ищет в DuckDuckGo и собирает URLs для скрейпинга"""
        
        urls_to_scrape = []
        seen_urls = set()
        
        with DDGS() as ddgs:
            for q in queries:
                logger.info(f"Searching DuckDuckGo: {q}")
                try:
                    results = list(ddgs.text(q, max_results=10))
                    logger.info(f"  → Got {len(results)} results")
                    
                    for r in results:
                        url = r.get('href', '')
                        if url and url not in seen_urls:
                            # Проверяем домен
                            domain = urlparse(url).netloc.lower()
                            
                            # Пропускаем заблокированные домены
                            if any(bd in domain for bd in self.blacklisted_domains):
                                logger.debug(f"  ✗ Skipping blacklisted domain: {domain}")
                                continue
                            
                            urls_to_scrape.append({
                                'url': url,
                                'title': r.get('title', ''),
                                'snippet': r.get('body', ''),
                                'query': q
                            })
                            seen_urls.add(url)
                    
                except Exception as e:
                    logger.error(f"Search error for '{q}': {e}")
                    continue
        
        return urls_to_scrape
    
    async def _scrape_websites(self, urls: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Скрейпит сайты параллельно и извлекает Telegram-каналы
        
        Returns:
            {username: {channel_data}}
        """
        
        # Ограничиваем количество сайтов (чтобы не тратить много времени)
        urls_to_process = urls[:30]  # Макс 30 сайтов
        
        logger.info(f"🌐 Scraping {len(urls_to_process)} websites...")
        
        # Параллельный скрейпинг
        tasks = [self._scrape_single_page(url_data) for url_data in urls_to_process]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Собираем все найденные каналы
        all_channels = {}
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error scraping {urls_to_process[i]['url']}: {result}")
                continue
            
            if result:
                for username, channel_data in result.items():
                    if username not in all_channels:
                        all_channels[username] = channel_data
        
        return all_channels
    
    async def _scrape_single_page(self, url_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """
        Скрейпит одну страницу и извлекает Telegram-каналы
        
        Returns:
            {username: {channel_data}}
        """
        url = url_data['url']
        logger.info(f"  📄 Scraping: {url[:80]}...")
        
        try:
            # HTTP запрос
            response = await self.http_client.get(url)
            response.raise_for_status()
            
            html = response.text
            logger.info(f"    ✓ Loaded {len(html)} chars")
            
            # Парсим HTML
            soup = BeautifulSoup(html, 'lxml')
            
            # Удаляем script и style теги (не нужны)
            for tag in soup(['script', 'style']):
                tag.decompose()
            
            # Получаем текст страницы
            page_text = soup.get_text()
            
            # Извлекаем каналы
            channels = self._extract_channels_from_html(soup, page_text, url_data)
            
            logger.info(f"    ✓ Extracted {len(channels)} channels")
            
            return channels
            
        except httpx.TimeoutException:
            logger.warning(f"    ✗ Timeout: {url[:60]}")
            return {}
        except httpx.HTTPStatusError as e:
            logger.warning(f"    ✗ HTTP {e.response.status_code}: {url[:60]}")
            return {}
        except Exception as e:
            logger.error(f"    ✗ Error: {e}")
            return {}
    
    def _extract_channels_from_html(
        self,
        soup: BeautifulSoup,
        page_text: str,
        url_data: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Извлекает Telegram-каналы из HTML
        
        Returns:
            {username: {channel_data}}
        """
        
        channels = {}
        
        # 1. ПРИОРИТЕТ: Ищем все t.me/ ссылки в <a> тегах
        telegram_links = soup.find_all('a', href=re.compile(r'(t\.me|telegram\.me)/'))
        
        for link in telegram_links:
            href = link.get('href', '')
            
            # Извлекаем username из ссылки
            match = re.search(r'(?:t\.me|telegram\.me)/([a-zA-Z0-9_]+)', href)
            if match:
                username = match.group(1)
                
                # Фильтруем
                if not self._is_valid_username(username):
                    continue
                
                # Получаем контекст вокруг ссылки
                link_text = link.get_text(strip=True)
                parent_text = link.parent.get_text(strip=True) if link.parent else ''
                
                if username not in channels:
                    channels[username] = {
                        'username': f"@{username}",
                        'title': link_text[:100] or username,
                        'description': parent_text[:200],
                        'source_url': url_data['url'],
                        'confidence': 'high'  # Прямая ссылка в <a> теге
                    }
        
        # 2. Ищем t.me/ упоминания в тексте (могут быть не в <a>)
        text_links = re.findall(r'(?:t\.me|telegram\.me)/([a-zA-Z0-9_]+)', page_text)
        
        for username in text_links:
            if not self._is_valid_username(username):
                continue
            
            if username not in channels:
                channels[username] = {
                    'username': f"@{username}",
                    'title': username,
                    'description': url_data.get('snippet', '')[:200],
                    'source_url': url_data['url'],
                    'confidence': 'medium'  # Упоминание в тексте
                }
        
        # 3. Ищем @username упоминания (только если в контексте Telegram)
        page_text_lower = page_text.lower()
        has_telegram_context = any(
            keyword in page_text_lower 
            for keyword in ['telegram', 't.me', 'телеграм', 'телеграмм', 'телега']
        )
        
        if has_telegram_context:
            mentions = re.findall(r'@([a-zA-Z][a-zA-Z0-9_]{4,31})', page_text)
            
            for username in set(mentions):  # set() для уникальности
                if not self._is_valid_username(username):
                    continue
                
                if username not in channels:
                    channels[username] = {
                        'username': f"@{username}",
                        'title': username,
                        'description': url_data.get('snippet', '')[:200],
                        'source_url': url_data['url'],
                        'confidence': 'low'  # Упоминание без t.me/
                    }
        
        return channels
    
    def _is_valid_username(self, username: str) -> bool:
        """Проверяет валидность Telegram username"""
        
        username_lower = username.lower()
        
        # 1. Черный список
        if username_lower in self.blacklisted_usernames:
            return False
        
        # 2. Длина
        if len(username) < 5 or len(username) > 32:
            return False
        
        # 3. Содержит точку (email-подобные)
        if '.' in username:
            return False
        
        # 4. Множественные подчеркивания (Instagram паттерн)
        if '___' in username or username.endswith('_') or username.startswith('_'):
            return False
        
        # 5. Длинные числа в конце (user12345)
        if re.search(r'\d{3,}$', username):
            return False
        
        # 6. Должен начинаться с буквы
        if not username[0].isalpha():
            return False
        
        return True
    
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
            
            import json
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
    
    async def close(self):
        """Закрывает HTTP клиент"""
        await self.http_client.aclose()




