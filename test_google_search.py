"""
Тест Google Custom Search API с переходом на сайты и извлечением Telegram ссылок

Показывает:
1. Поисковые запросы к Google API
2. Полученные результаты (URLs, titles, snippets)
3. Переход на каждый сайт
4. Парсинг HTML
5. Извлеченные Telegram ссылки
"""

import asyncio
import logging
import sys
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# Настройка логирования
Path("logs").mkdir(exist_ok=True)

log_file = f'logs/google_search_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Импорт конфига
from config import settings


class GoogleSearchTester:
    """Тестер Google Custom Search API с web scraping"""
    
    def __init__(self):
        self.api_key = settings.google_search_api_key
        self.engine_id = settings.google_search_engine_id
        self.api_url = "https://www.googleapis.com/customsearch/v1"
        
        if not self.api_key:
            raise ValueError("GOOGLE_SEARCH_API_KEY not set in .env")
        if not self.engine_id:
            raise ValueError("GOOGLE_SEARCH_ENGINE_ID not set in .env")
        
        # HTTP клиент для скрейпинга
        self.http_client = httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            }
        )
        
        # Черный список доменов
        self.blacklisted_domains = {
            'instagram.com', 'facebook.com', 'twitter.com', 'x.com',
            'youtube.com', 'tiktok.com', 'linkedin.com', 'reddit.com',
            'pinterest.com', 'amazon.com', 'ebay.com'
        }
        
        # Черный список username
        self.blacklisted_usernames = {
            'gmail', 'mail', 'yandex', 'yahoo', 'outlook', 'hotmail', 'icloud',
            'instagram', 'facebook', 'twitter', 'tiktok', 'youtube', 'linkedin',
            'magenta', 'telekom', 'katyperry', 'justinbieber'
        }
    
    async def search_google(self, query: str, num_results: int = 10) -> List[Dict[str, Any]]:
        """
        Ищет в Google Custom Search API
        
        Args:
            query: Поисковый запрос
            num_results: Количество результатов (макс 10 за запрос)
            
        Returns:
            Список результатов поиска
        """
        logger.info(f"\n{'='*100}")
        logger.info(f"🔍 GOOGLE SEARCH: {query}")
        logger.info(f"{'='*100}")
        
        params = {
            'key': self.api_key,
            'cx': self.engine_id,
            'q': query,
            'num': min(num_results, 10)  # Google API максимум 10 за запрос
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.api_url, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                # Извлекаем результаты
                items = data.get('items', [])
                logger.info(f"✅ Got {len(items)} results from Google API")
                
                results = []
                for i, item in enumerate(items, 1):
                    result = {
                        'title': item.get('title', ''),
                        'link': item.get('link', ''),
                        'snippet': item.get('snippet', ''),
                        'displayLink': item.get('displayLink', '')
                    }
                    results.append(result)
                    
                    logger.info(f"\n  Result {i}:")
                    logger.info(f"    Title:  {result['title'][:80]}")
                    logger.info(f"    URL:    {result['link'][:80]}")
                    logger.info(f"    Domain: {result['displayLink']}")
                    logger.info(f"    Snippet: {result['snippet'][:100]}")
                
                return results
                
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP Error: {e.response.status_code}")
            logger.error(f"   Response: {e.response.text[:500]}")
            return []
        except Exception as e:
            logger.error(f"❌ Error searching Google: {e}")
            return []
    
    async def scrape_website(self, url: str) -> Dict[str, Any]:
        """
        Скрейпит один сайт и извлекает Telegram ссылки
        
        Returns:
            {
                'url': url,
                'success': bool,
                'channels_found': int,
                'channels': List[Dict]
            }
        """
        logger.info(f"\n  📄 Scraping: {url[:80]}...")
        
        # Проверяем домен
        domain = urlparse(url).netloc.lower()
        if any(bd in domain for bd in self.blacklisted_domains):
            logger.info(f"    ✗ Skipping blacklisted domain: {domain}")
            return {
                'url': url,
                'success': False,
                'reason': 'blacklisted_domain',
                'channels_found': 0,
                'channels': []
            }
        
        try:
            response = await self.http_client.get(url)
            response.raise_for_status()
            
            html = response.text
            logger.info(f"    ✓ Loaded {len(html)} chars")
            
            # Парсим HTML
            soup = BeautifulSoup(html, 'lxml')
            
            # Удаляем script и style
            for tag in soup(['script', 'style']):
                tag.decompose()
            
            # Извлекаем каналы
            channels = self._extract_telegram_channels(soup, html, url)
            
            logger.info(f"    ✓ Found {len(channels)} Telegram channels")
            
            if channels:
                for ch in channels[:5]:  # Показываем первые 5
                    logger.info(f"      • {ch['username']:30s} - {ch.get('title', '')[:50]}")
                if len(channels) > 5:
                    logger.info(f"      ... and {len(channels) - 5} more")
            
            return {
                'url': url,
                'success': True,
                'channels_found': len(channels),
                'channels': channels
            }
            
        except httpx.TimeoutException:
            logger.warning(f"    ✗ Timeout")
            return {
                'url': url,
                'success': False,
                'reason': 'timeout',
                'channels_found': 0,
                'channels': []
            }
        except httpx.HTTPStatusError as e:
            logger.warning(f"    ✗ HTTP {e.response.status_code}")
            return {
                'url': url,
                'success': False,
                'reason': f'http_{e.response.status_code}',
                'channels_found': 0,
                'channels': []
            }
        except Exception as e:
            logger.warning(f"    ✗ Error: {e}")
            return {
                'url': url,
                'success': False,
                'reason': str(e),
                'channels_found': 0,
                'channels': []
            }
    
    def _extract_telegram_channels(
        self,
        soup: BeautifulSoup,
        html: str,
        source_url: str
    ) -> List[Dict[str, Any]]:
        """Извлекает Telegram каналы из HTML"""
        
        channels = {}
        
        # 1. ПРИОРИТЕТ: Ищем все t.me/ ссылки в <a> тегах
        telegram_links = soup.find_all('a', href=re.compile(r'(t\.me|telegram\.me)/'))
        
        for link in telegram_links:
            href = link.get('href', '')
            
            # Извлекаем username
            match = re.search(r'(?:t\.me|telegram\.me)/([a-zA-Z0-9_]+)', href)
            if match:
                username = match.group(1)
                
                if not self._is_valid_username(username):
                    continue
                
                # Получаем контекст
                link_text = link.get_text(strip=True)
                parent_text = link.parent.get_text(strip=True) if link.parent else ''
                
                if username not in channels:
                    channels[username] = {
                        'username': f"@{username}",
                        'title': link_text[:100] or username,
                        'description': parent_text[:200],
                        'source_url': source_url,
                        'confidence': 'high'
                    }
        
        # 2. Ищем t.me/ упоминания в тексте
        text_links = re.findall(r'(?:t\.me|telegram\.me)/([a-zA-Z0-9_]+)', html)
        
        for username in text_links:
            if not self._is_valid_username(username):
                continue
            
            if username not in channels:
                channels[username] = {
                    'username': f"@{username}",
                    'title': username,
                    'description': '',
                    'source_url': source_url,
                    'confidence': 'medium'
                }
        
        # 3. Ищем @username упоминания (только если есть Telegram контекст)
        html_lower = html.lower()
        has_telegram_context = any(
            keyword in html_lower
            for keyword in ['telegram', 't.me', 'телеграм', 'телеграмм', 'телега']
        )
        
        if has_telegram_context:
            mentions = re.findall(r'@([a-zA-Z][a-zA-Z0-9_]{4,31})', html)
            
            for username in set(mentions):
                if not self._is_valid_username(username):
                    continue
                
                if username not in channels:
                    channels[username] = {
                        'username': f"@{username}",
                        'title': username,
                        'description': '',
                        'source_url': source_url,
                        'confidence': 'low'
                    }
        
        return list(channels.values())
    
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
    
    async def test_full_flow(self, queries: List[str]):
        """
        Полный тест: поиск → скрейпинг → извлечение
        
        Args:
            queries: Список поисковых запросов
        """
        logger.info("=" * 100)
        logger.info("🚀 GOOGLE SEARCH API TEST WITH WEB SCRAPING")
        logger.info("=" * 100)
        logger.info(f"\nAPI Key: {self.api_key[:10]}...")
        logger.info(f"Engine ID: {self.engine_id[:10]}...")
        logger.info(f"Queries to test: {len(queries)}")
        
        all_channels = {}
        all_scrape_results = []
        
        # 1. Ищем в Google
        for query in queries:
            search_results = await self.search_google(query, num_results=5)
            
            if not search_results:
                logger.warning(f"  ⚠️ No results for query: {query}")
                continue
            
            # 2. Скрейпим каждый сайт
            logger.info(f"\n  🌐 Scraping {len(search_results)} websites...")
            
            scrape_tasks = [self.scrape_website(r['link']) for r in search_results]
            scrape_results = await asyncio.gather(*scrape_tasks, return_exceptions=True)
            
            for i, result in enumerate(scrape_results):
                if isinstance(result, Exception):
                    logger.error(f"    ✗ Exception: {result}")
                    continue
                
                all_scrape_results.append({
                    'query': query,
                    'search_result': search_results[i],
                    'scrape_result': result
                })
                
                # Собираем каналы
                for ch in result.get('channels', []):
                    username = ch['username']
                    if username not in all_channels:
                        all_channels[username] = ch
            
            # Небольшая задержка между запросами (чтобы не превысить лимиты)
            await asyncio.sleep(1)
        
        # Финальный отчет
        logger.info("\n" + "=" * 100)
        logger.info("📊 FINAL REPORT")
        logger.info("=" * 100)
        
        logger.info(f"\nQueries tested: {len(queries)}")
        logger.info(f"Websites scraped: {len(all_scrape_results)}")
        logger.info(f"Successful scrapes: {sum(1 for r in all_scrape_results if r['scrape_result'].get('success'))}")
        logger.info(f"Total channels found: {len(all_channels)}")
        
        if all_channels:
            logger.info("\n✅ All found Telegram channels:")
            logger.info("=" * 100)
            for i, (username, ch) in enumerate(sorted(all_channels.items()), 1):
                logger.info(
                    f"{i:3d}. {ch['username']:30s} | "
                    f"Confidence: {ch['confidence']:6s} | "
                    f"{ch.get('title', '')[:50]}"
                )
        else:
            logger.warning("⚠️ No Telegram channels found!")
        
        # Сохраняем детальный отчет
        report = {
            'timestamp': datetime.now().isoformat(),
            'queries': queries,
            'scrape_results': all_scrape_results,
            'channels': list(all_channels.values()),
            'summary': {
                'queries_tested': len(queries),
                'websites_scraped': len(all_scrape_results),
                'successful_scrapes': sum(1 for r in all_scrape_results if r['scrape_result'].get('success')),
                'channels_found': len(all_channels)
            }
        }
        
        report_file = f"logs/google_search_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n💾 Detailed report saved to: {report_file}")
        logger.info(f"📄 Full log saved to: {log_file}")
        
        return all_channels
    
    async def close(self):
        """Закрывает HTTP клиент"""
        await self.http_client.aclose()


async def main():
    """Главная функция теста"""
    
    # Тестовые запросы
    test_queries = [
        "Казань telegram группа",
        "telegram чат Казань общение",
        "t.me kazan chat"
    ]
    
    try:
        tester = GoogleSearchTester()
        
        await tester.test_full_flow(test_queries)
        
    except ValueError as e:
        logger.error(f"❌ Configuration error: {e}")
        logger.error("\nPlease set in .env:")
        logger.error("  GOOGLE_SEARCH_API=your_api_key")
        logger.error("  GOOGLE_SEARCH_ENGINE_ID=your_engine_id")
        logger.error("\nTo get Engine ID:")
        logger.error("  1. Go to https://programmablesearchengine.google.com/")
        logger.error("  2. Create a new search engine")
        logger.error("  3. Set 'Sites to search' to 'Search the entire web'")
        logger.error("  4. Copy the 'Search engine ID' (cx parameter)")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if 'tester' in locals():
            await tester.close()


if __name__ == "__main__":
    asyncio.run(main())

