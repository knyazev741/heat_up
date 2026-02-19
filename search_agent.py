"""
SearchAgent - REAL web search для Telegram каналов через Google Custom Search API
"""

import re
import logging
import asyncio
from typing import Dict, Any, List
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
from openai import OpenAI
from config import settings
import json

logger = logging.getLogger(__name__)


class SearchAgent:
    """
    Агент поиска РЕАЛЬНЫХ Telegram-чатов через Google Custom Search API
    
    1. Генерирует разные поисковые запросы (город + интересы)
    2. Ищет в Google Custom Search API
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
        
        # Google Custom Search API
        self.google_api_key = settings.google_search_api_key
        self.google_engine_id = settings.google_search_engine_id
        self.google_api_url = "https://www.googleapis.com/customsearch/v1"
        
        if not self.google_api_key or not self.google_engine_id:
            logger.warning("Google Search API not configured - search will be limited")
        
        # HTTP клиент для web scraping
        self.http_client = httpx.AsyncClient(
            timeout=15.0,
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
    
    async def find_relevant_chats(
        self,
        persona: Dict[str, Any],
        limit: int = 20,
        failed_queries: List[str] = None,
        account_id: int = None
    ) -> List[Dict[str, Any]]:
        """
        Ищет УНИКАЛЬНЫЕ Telegram-чаты через Google + web scraping.

        КРИТИЧНО: Проверяет что найденные каналы НЕ заняты другими warmup аккаунтами.
        Если все заняты - генерирует НОВЫЕ запросы через LLM.

        Args:
            persona: Словарь с данными персоны
            limit: Максимальное количество чатов
            failed_queries: Предыдущие запросы которые не сработали
            account_id: ID аккаунта для проверки эксклюзивности

        Returns:
            Список УНИКАЛЬНЫХ чатов (не занятых другими warmup)
        """
        logger.info(f"🔍 Searching UNIQUE chats for: {persona.get('generated_name')} (no city!)")

        if not self.google_api_key or not self.google_engine_id:
            logger.error("Google Search API not configured!")
            return []

        # Получаем список каналов занятых другими warmup аккаунтами
        occupied_channels = []
        if account_id:
            occupied_channels = self._get_occupied_channels(account_id)
            if occupied_channels:
                logger.info(f"🔒 {len(occupied_channels)} channels occupied by other warmup accounts")

        all_used_queries = list(failed_queries or [])
        max_retries = 3
        final_results = []

        for attempt in range(max_retries):
            logger.info(f"📍 Search attempt {attempt + 1}/{max_retries}")

            # ВСЕГДА используем LLM для уникальных запросов
            queries = await self._generate_smart_queries(
                persona,
                all_used_queries,
                occupied_channels if attempt > 0 else None  # После первой попытки передаём занятые
            )

            if not queries:
                logger.warning("LLM failed to generate queries, using fallback")
                queries = self._generate_search_queries(persona)

            all_used_queries.extend(queries)
            logger.info(f"Generated {len(queries)} queries")

            # Поиск Google
            urls_to_scrape = await self._search_google(queries)
            if not urls_to_scrape:
                logger.warning("No URLs from Google, retrying...")
                continue

            # Скрейпинг
            all_channels = await self._scrape_websites(urls_to_scrape)
            if not all_channels:
                logger.warning("No channels from scraping, retrying...")
                continue

            # Фильтруем занятые каналы
            available_channels = {}
            for username, data in all_channels.items():
                clean_username = username.lower().replace('@', '')
                if not any(clean_username == occ.lower().replace('@', '') for occ in occupied_channels):
                    available_channels[username] = data
                else:
                    logger.debug(f"  ✗ Skipping occupied: {username}")

            logger.info(f"📊 Found {len(all_channels)} channels, {len(available_channels)} available (not occupied)")

            if available_channels:
                # LLM ранжирование
                ranked = await self._rank_chats_with_llm(persona, list(available_channels.values()))
                final_results.extend(ranked)

                # Добавляем найденные в список занятых для следующих итераций
                for chat in ranked:
                    username = chat.get('username', '').replace('@', '')
                    if username:
                        occupied_channels.append(username)

            if len(final_results) >= limit:
                break

            if attempt < max_retries - 1:
                logger.info(f"🔄 Need more unique channels, retrying with different queries...")

        logger.info(f"✅ Final: {len(final_results)} unique available channels")
        return final_results[:limit]

    def _get_occupied_channels(self, account_id: int) -> List[str]:
        """Получает список каналов занятых другими warmup аккаунтами"""
        try:
            from database import get_db_connection
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT dc.chat_username
                    FROM discovered_chats dc
                    JOIN accounts a ON dc.account_id = a.id
                    WHERE dc.is_joined = 1
                    AND a.account_type = 'warmup'
                    AND a.is_active = 1
                    AND a.is_frozen = 0
                    AND a.is_deleted = 0
                    AND dc.account_id != ?
                """, (account_id,))
                return [row['chat_username'].replace('@', '') for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error getting occupied channels: {e}")
            return []
    
    async def _generate_smart_queries(
        self,
        persona: Dict[str, Any],
        failed_queries: List[str],
        occupied_channels: List[str] = None
    ) -> List[str]:
        """
        Использует LLM для генерации УНИКАЛЬНЫХ поисковых запросов.

        КРИТИЧНО: НЕ использует город! Только интересы и хобби.
        Это предотвращает нахождение одних и тех же каналов разными аккаунтами.

        Args:
            persona: Данные персоны
            failed_queries: Запросы которые уже пробовали
            occupied_channels: Каналы уже занятые другими warmup аккаунтами

        Returns:
            Список уникальных запросов
        """
        interests = persona.get('interests', [])
        occupation = persona.get('occupation', '')
        hobbies = persona.get('hobbies', interests)
        personality = persona.get('personality_traits', [])

        failed_list = "\n".join([f"  - {q}" for q in failed_queries[:15]]) if failed_queries else "Нет"
        occupied_list = "\n".join([f"  - {ch}" for ch in (occupied_channels or [])[:20]]) if occupied_channels else "Нет"

        prompt = f"""Придумай УНИКАЛЬНЫЕ поисковые запросы для Google чтобы найти Telegram-группы.

ИНТЕРЕСЫ ЧЕЛОВЕКА:
- Профессия: {occupation or 'не указана'}
- Интересы: {', '.join(interests[:6]) if interests else 'разные'}
- Хобби: {', '.join(hobbies[:6]) if hobbies else 'разные'}
- Характер: {', '.join(personality[:3]) if personality else 'общительный'}

ПРЕДЫДУЩИЕ ЗАПРОСЫ (НЕ ПОВТОРЯЙ!):
{failed_list}

КАНАЛЫ КОТОРЫЕ УЖЕ ЗАНЯТЫ (нужны ДРУГИЕ!):
{occupied_list}

ЗАДАЧА:
Придумай 10 УНИКАЛЬНЫХ поисковых запросов чтобы найти Telegram-ГРУППЫ для общения.

КРИТИЧНЫЕ ПРАВИЛА:
1. НЕ используй названия городов или регионов!
2. Фокусируйся ТОЛЬКО на интересах и хобби
3. Ищи НИШЕВЫЕ группы - узкоспециализированные сообщества
4. Каждый запрос должен быть про РАЗНЫЕ темы
5. Используй специфичные термины из хобби
6. Ищи группы для обсуждений, не новостные каналы

ПРИМЕРЫ ХОРОШИХ ЗАПРОСОВ:
- "telegram группа любителей комнатных растений чат"
- "t.me сообщество ретро игры обсуждение"
- "telegram чат фотографы природа"

ФОРМАТ - только запросы, по одному на строку:
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=0.95,  # Высокая креативность
                max_tokens=600,
                messages=[
                    {"role": "system", "content": "Генерируй только уникальные поисковые запросы. Без городов и регионов!"},
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = response.choices[0].message.content.strip()

            queries = []
            for line in response_text.split('\n'):
                line = line.strip()
                line = re.sub(r'^[\d]+[.\)]\s*', '', line)
                line = re.sub(r'^[-•]\s*', '', line)
                if line and len(line) > 5 and line not in (failed_queries or []):
                    queries.append(line)

            logger.info(f"🧠 LLM generated {len(queries)} unique queries (no city!)")
            return queries[:15]

        except Exception as e:
            logger.error(f"Error generating smart queries: {e}")
            return self._generate_search_queries(persona)

    def _generate_search_queries(self, persona: Dict[str, Any]) -> List[str]:
        """
        Генерирует базовые поисковые запросы БЕЗ ГОРОДА.

        КРИТИЧНО: Не используем город чтобы разные аккаунты не находили
        одни и те же региональные каналы.
        """
        interests = persona.get('interests', [])
        occupation = persona.get('occupation', '')
        hobbies = persona.get('hobbies', interests)

        queries = []

        # ТЕМАТИЧЕСКИЕ ГРУППЫ по интересам (без города!)
        for interest in interests[:5]:
            queries.extend([
                f"telegram группа {interest} обсуждение чат",
                f"t.me {interest} сообщество группа",
                f"telegram chat {interest} community",
            ])

        # ХОББИ группы
        for hobby in hobbies[:3]:
            if hobby not in interests:
                queries.append(f"telegram группа любителей {hobby}")

        # ПРОФЕССИОНАЛЬНЫЕ группы
        if occupation:
            queries.extend([
                f"telegram группа {occupation} общение",
                f"telegram чат {occupation} сообщество профессионалы",
            ])

        # Общие тематические
        queries.extend([
            "telegram группа по интересам общение",
            "t.me публичная группа чат обсуждение",
        ])

        return queries[:15]
    
    async def _search_google(self, queries: List[str]) -> List[Dict[str, Any]]:
        """
        Ищет в Google Custom Search API и собирает URLs для скрейпинга
        
        Args:
            queries: Список поисковых запросов
            
        Returns:
            Список словарей с URL и метаданными для скрейпинга
        """
        urls_to_scrape = []
        seen_urls = set()
        
        for q in queries:
            logger.info(f"Searching Google: {q}")
            
            if not self.google_api_key or not self.google_engine_id:
                continue
            
            params = {
                'key': self.google_api_key,
                'cx': self.google_engine_id,
                'q': q,
                'num': 10  # Максимум 10 результатов за запрос
            }
            
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(self.google_api_url, params=params)
                    response.raise_for_status()
                    
                    data = response.json()
                    items = data.get('items', [])
                    logger.info(f"  → Got {len(items)} results from Google API")
                    
                    for item in items:
                        url = item.get('link', '')
                        if url and url not in seen_urls:
                            # Проверяем домен
                            domain = urlparse(url).netloc.lower()
                            
                            # Пропускаем заблокированные домены
                            if any(bd in domain for bd in self.blacklisted_domains):
                                logger.debug(f"  ✗ Skipping blacklisted domain: {domain}")
                                continue
                            
                            urls_to_scrape.append({
                                'url': url,
                                'title': item.get('title', ''),
                                'snippet': item.get('snippet', ''),
                                'displayLink': item.get('displayLink', ''),
                                'query': q
                            })
                            seen_urls.add(url)
                    
                    # Небольшая задержка между запросами (чтобы не превысить лимиты)
                    await asyncio.sleep(0.5)
                    
            except httpx.HTTPStatusError as e:
                logger.error(f"  ✗ HTTP Error {e.response.status_code} for query '{q}': {e.response.text[:200]}")
                continue
            except Exception as e:
                logger.error(f"  ✗ Error searching Google for '{q}': {e}")
                continue
        
        return urls_to_scrape
    
    async def _scrape_websites(self, urls: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Скрейпит сайты параллельно и извлекает Telegram-каналы
        
        Args:
            urls: Список словарей с URL и метаданными
            
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
        
        Args:
            url_data: Словарь с URL и метаданными
            
        Returns:
            {username: {channel_data}}
        """
        url = url_data['url']
        logger.debug(f"  📄 Scraping: {url[:80]}...")
        
        try:
            response = await self.http_client.get(url)
            response.raise_for_status()
            
            html = response.text
            logger.debug(f"    ✓ Loaded {len(html)} chars")
            
            # Парсим HTML
            soup = BeautifulSoup(html, 'lxml')
            
            # Удаляем script и style теги
            for tag in soup(['script', 'style']):
                tag.decompose()
            
            # Получаем текст страницы
            page_text = soup.get_text()
            
            # Извлекаем каналы
            channels = self._extract_channels_from_html(soup, page_text, url_data)
            
            if channels:
                logger.debug(f"    ✓ Extracted {len(channels)} channels")
            
            return channels
            
        except httpx.TimeoutException:
            logger.debug(f"    ✗ Timeout: {url[:60]}")
            return {}
        except httpx.HTTPStatusError as e:
            logger.debug(f"    ✗ HTTP {e.response.status_code}: {url[:60]}")
            return {}
        except Exception as e:
            logger.debug(f"    ✗ Error: {e}")
            return {}
    
    def _extract_channels_from_html(
        self,
        soup: BeautifulSoup,
        page_text: str,
        url_data: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Извлекает Telegram-каналы из HTML
        
        Args:
            soup: BeautifulSoup объект
            page_text: Текст страницы
            url_data: Метаданные URL
            
        Returns:
            {username: {channel_data}}
        """
        
        channels = {}
        
        # Черный список username
        blacklist = {
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
            'katyperry', 'justinbieber', 'arianagrande', 'selenagomez',
            'telegram',  # Общий канал Telegram
            # TGStat и связанные каналы/боты — КРИТИЧНО! Вступление в них связывает аккаунты!
            'tgstat', 'tgstat_chat', 'tgstatapi', 'tgstat_bot', 'tgstatchatbot',
            'tgalertsbot', 'tg_analytics_bot', 'searcheebot', 'telepulse',
            'share',  # Популярный канал с пересечениями
        }
        
        # 1. ПРИОРИТЕТ: Ищем все t.me/ ссылки в <a> тегах
        telegram_links = soup.find_all('a', href=re.compile(r'(t\.me|telegram\.me)/'))
        
        for link in telegram_links:
            href = link.get('href', '')
            
            # Извлекаем username
            match = re.search(r'(?:t\.me|telegram\.me)/([a-zA-Z0-9_]+)', href)
            if match:
                username = match.group(1)
                
                if not self._is_valid_username(username, blacklist):
                    continue
                
                # Получаем контекст
                link_text = link.get_text(strip=True)
                parent_text = link.find_parent().get_text(strip=True) if link.find_parent() else ''
                
                if username not in channels:
                    channels[username] = {
                        'username': f"@{username}",
                        'title': link_text[:100] or url_data.get('title', '')[:100] or username,
                        'description': parent_text[:200] or url_data.get('snippet', '')[:200],
                        'source_url': url_data['url'],
                        'confidence': 'high'
                    }
        
        # 2. Ищем t.me/ упоминания в тексте
        text_links = re.findall(r'(?:t\.me|telegram\.me)/([a-zA-Z0-9_]+)', page_text)
        
        for username in set(text_links):  # set() для уникальности
            if not self._is_valid_username(username, blacklist):
                continue
            
            if username not in channels:
                channels[username] = {
                    'username': f"@{username}",
                    'title': username,
                    'description': url_data.get('snippet', '')[:200],
                    'source_url': url_data['url'],
                    'confidence': 'medium'
                }
        
        # 3. Ищем @username упоминания (только если есть Telegram контекст)
        page_text_lower = page_text.lower()
        has_telegram_context = any(
            keyword in page_text_lower
            for keyword in ['telegram', 't.me', 'телеграм', 'телеграмм', 'телега']
        )
        
        if has_telegram_context:
            mentions = re.findall(r'@([a-zA-Z][a-zA-Z0-9_]{4,31})', page_text)
            
            for username in set(mentions):
                if not self._is_valid_username(username, blacklist):
                    continue
                
                if username not in channels:
                    channels[username] = {
                        'username': f"@{username}",
                        'title': username,
                        'description': url_data.get('snippet', '')[:200],
                        'source_url': url_data['url'],
                        'confidence': 'low'
                    }
        
        return channels
    
    def _is_valid_username(self, username: str, blacklist: set) -> bool:
        """Проверяет валидность Telegram username"""
        
        username_lower = username.lower()
        
        if username_lower in blacklist:
            return False
        
        if len(username) < 5 or len(username) > 32:
            return False
        
        if '.' in username or '___' in username:
            return False
        
        if username.endswith('_') or username.startswith('_'):
            return False
        
        if re.search(r'\d{3,}$', username):
            return False
        
        if not username[0].isalpha():
            return False
        
        return True
    
    async def close(self):
        """Закрывает HTTP клиент"""
        await self.http_client.aclose()
    
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
