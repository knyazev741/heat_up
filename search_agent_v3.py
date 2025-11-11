"""
SearchAgent V3 - скрейпит каталоги Telegram каналов напрямую

Источники:
- tlgrm.ru - крупный русский каталог
- tgstat.ru - статистика каналов
- Другие каталоги

Логика:
1. Генерирует URL для скрейпинга (город, категория)
2. Скрейпит каталоги
3. Извлекает каналы
4. LLM ранжирует
"""

import re
import logging
import asyncio
from typing import Dict, Any, List
from openai import OpenAI
from config import settings
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote

logger = logging.getLogger(__name__)


class SearchAgentV3:
    """
    Агент поиска через каталоги Telegram каналов
    """
    
    def __init__(self):
        # Using DeepSeek API (OpenAI-compatible)
        self.client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com"
        )
        self.model = "deepseek-chat"
        
        # HTTP клиент
        self.http_client = httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            }
        )
        
        # Маппинг городов на английский для URL
        self.city_mapping = {
            "Москва": "moscow",
            "Санкт-Петербург": "saint-petersburg",
            "Казань": "kazan",
            "Екатеринбург": "ekaterinburg",
            "Нижний Новгород": "nizhny-novgorod",
            "Новосибирск": "novosibirsk",
            "Самара": "samara",
            "Омск": "omsk",
            "Красноярск": "krasnoyarsk",
            "Воронеж": "voronezh",
            "Пермь": "perm",
            "Волгоград": "volgograd",
            "Краснодар": "krasnodar",
            "Саратов": "saratov",
            "Тюмень": "tyumen",
            "Тольятти": "tolyatti",
            "Ижевск": "izhevsk",
            "Барнаул": "barnaul",
            "Ульяновск": "ulyanovsk",
            "Иркутск": "irkutsk",
            "Хабаровск": "khabarovsk",
            "Ярославль": "yaroslavl",
            "Владивосток": "vladivostok",
            "Махачкала": "makhachkala",
            "Томск": "tomsk",
            "Оренбург": "orenburg",
            "Кемерово": "kemerovo",
            "Новокузнецк": "novokuznetsk",
            "Рязань": "ryazan",
            "Астрахань": "astrakhan",
            "Набережные Челны": "naberezhnye-chelny",
            "Пенза": "penza",
            "Липецк": "lipetsk",
            "Киров": "kirov",
            "Чебоксары": "cheboksary",
            "Тверь": "tver",
            "Калининград": "kaliningrad",
            "Брянск": "bryansk",
            "Иваново": "ivanovo",
            "Магнитогорск": "magnitogorsk",
            "Курск": "kursk",
            "Сочи": "sochi",
            "Ставрополь": "stavropol",
            "Улан-Удэ": "ulan-ude",
            "Тула": "tula",
            "Вологда": "vologda"
        }
        
        # Черный список
        self.blacklisted_usernames = {
            'gmail', 'mail', 'yandex', 'yahoo', 'outlook', 'hotmail', 'icloud',
            'instagram', 'facebook', 'twitter', 'tiktok', 'youtube', 'linkedin',
            'magenta', 'telekom', 'katyperry', 'justinbieber'
        }
    
    async def find_relevant_chats(
        self,
        persona: Dict[str, Any],
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Ищет Telegram-чаты через каталоги
        
        Args:
            persona: Словарь с данными персоны
            limit: Максимальное количество чатов
            
        Returns:
            Список чатов с метаданными
        """
        logger.info(f"🔍 Searching Telegram chats for: {persona.get('generated_name')}")
        
        city = persona.get('city', 'Москва')
        interests = persona.get('interests', [])
        
        logger.info(f"City: {city}, Interests: {interests[:3]}")
        
        # Генерируем URLs для скрейпинга
        urls_to_scrape = self._generate_catalog_urls(city, interests)
        logger.info(f"Generated {len(urls_to_scrape)} catalog URLs to scrape")
        
        # Скрейпим каталоги
        all_channels = await self._scrape_catalogs(urls_to_scrape)
        logger.info(f"Found {len(all_channels)} UNIQUE channels")
        
        if not all_channels:
            logger.warning("No channels found via catalogs!")
            return []
        
        # LLM ранжирует по релевантности
        ranked_chats = await self._rank_chats_with_llm(persona, list(all_channels.values()))
        
        return ranked_chats[:limit]
    
    def _generate_catalog_urls(self, city: str, interests: List[str]) -> List[Dict[str, Any]]:
        """Генерирует URLs каталогов для скрейпинга"""
        
        urls = []
        
        # 1. TLGRM.RU - поиск по городу
        city_en = self.city_mapping.get(city, city.lower())
        
        urls.append({
            'url': f"https://tlgrm.ru/channels?search={quote(city)}",
            'source': 'tlgrm.ru',
            'type': 'city_search',
            'city': city
        })
        
        # 2. Поиск по интересам
        for interest in interests[:3]:
            urls.append({
                'url': f"https://tlgrm.ru/channels?search={quote(interest)}",
                'source': 'tlgrm.ru',
                'type': 'interest_search',
                'interest': interest
            })
        
        # 3. TGSTAT.RU - каталог
        urls.append({
            'url': f"https://tgstat.ru/search?q={quote(city)}",
            'source': 'tgstat.ru',
            'type': 'city_search',
            'city': city
        })
        
        return urls
    
    async def _scrape_catalogs(self, urls: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Скрейпит каталоги параллельно"""
        
        logger.info(f"🌐 Scraping {len(urls)} catalog pages...")
        
        # Параллельный скрейпинг
        tasks = [self._scrape_catalog_page(url_data) for url_data in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Собираем все найденные каналы
        all_channels = {}
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error scraping {urls[i]['url']}: {result}")
                continue
            
            if result:
                for username, channel_data in result.items():
                    if username not in all_channels:
                        all_channels[username] = channel_data
        
        return all_channels
    
    async def _scrape_catalog_page(self, url_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Скрейпит одну страницу каталога"""
        
        url = url_data['url']
        source = url_data['source']
        
        logger.info(f"  📄 Scraping {source}: {url[:80]}...")
        
        try:
            response = await self.http_client.get(url)
            response.raise_for_status()
            
            html = response.text
            logger.info(f"    ✓ Loaded {len(html)} chars")
            
            soup = BeautifulSoup(html, 'lxml')
            
            # Извлекаем каналы в зависимости от источника
            if source == 'tlgrm.ru':
                channels = self._extract_from_tlgrm(soup, url_data)
            elif source == 'tgstat.ru':
                channels = self._extract_from_tgstat(soup, url_data)
            else:
                channels = {}
            
            logger.info(f"    ✓ Extracted {len(channels)} channels")
            
            return channels
            
        except Exception as e:
            logger.warning(f"    ✗ Error: {e}")
            return {}
    
    def _extract_from_tlgrm(self, soup: BeautifulSoup, url_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Извлекает каналы с tlgrm.ru"""
        
        channels = {}
        
        # Ищем все ссылки t.me/
        links = soup.find_all('a', href=re.compile(r't\.me/'))
        
        for link in links:
            href = link.get('href', '')
            
            # Извлекаем username
            match = re.search(r't\.me/([a-zA-Z0-9_]+)', href)
            if not match:
                continue
            
            username = match.group(1)
            
            if not self._is_valid_username(username):
                continue
            
            # Пытаемся найти описание канала рядом
            title = link.get_text(strip=True) or username
            description = ""
            
            # Ищем parent элемент с описанием
            parent = link.find_parent('div', class_=re.compile(r'channel|item|card'))
            if parent:
                description = parent.get_text(strip=True)[:200]
            
            channels[username] = {
                'username': f"@{username}",
                'title': title[:100],
                'description': description,
                'source_url': url_data['url'],
                'confidence': 'high'
            }
        
        return channels
    
    def _extract_from_tgstat(self, soup: BeautifulSoup, url_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Извлекает каналы с tgstat.ru"""
        
        channels = {}
        
        # Ищем все ссылки t.me/
        links = soup.find_all('a', href=re.compile(r'(t\.me/|tgstat\.ru/channel/)'))
        
        for link in links:
            href = link.get('href', '')
            
            # Извлекаем username
            match = re.search(r'(?:t\.me|tgstat\.ru/channel)/([a-zA-Z0-9_]+)', href)
            if not match:
                continue
            
            username = match.group(1)
            
            if not self._is_valid_username(username):
                continue
            
            title = link.get_text(strip=True) or username
            
            channels[username] = {
                'username': f"@{username}",
                'title': title[:100],
                'description': '',
                'source_url': url_data['url'],
                'confidence': 'high'
            }
        
        return channels
    
    def _is_valid_username(self, username: str) -> bool:
        """Проверяет валидность Telegram username"""
        
        username_lower = username.lower()
        
        if username_lower in self.blacklisted_usernames:
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
    
    async def _rank_chats_with_llm(
        self,
        persona: Dict[str, Any],
        channels: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """LLM оценивает релевантность каналов"""
        
        if not channels:
            return []
        
        channels_for_llm = channels[:30]
        
        channels_list = "\n".join([
            f"{i+1}. {ch['username']} - {ch['title']}"
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
            
            for i, chat in enumerate(sorted(ranked_chats, key=lambda x: x['relevance_score'], reverse=True)[:5]):
                logger.info(f"  {i+1}. {chat['chat_username']} (score: {chat['relevance_score']:.2f})")
            
            return ranked_chats
            
        except Exception as e:
            logger.error(f"Error ranking chats: {e}")
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




