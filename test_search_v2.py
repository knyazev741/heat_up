"""
Тест SearchAgentV2 с детальным логированием
Показывает: поисковые запросы → URLs → скрейпинг → извлеченные каналы → LLM ранжирование
"""

import asyncio
import logging
import sys
import json
from datetime import datetime
from pathlib import Path

# Настройка детального логирования
Path("logs").mkdir(exist_ok=True)

log_file = f'logs/search_v2_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Импорт
from database import get_all_accounts, get_persona
from search_agent_v2 import SearchAgentV2
from config import settings


async def test_search_v2(account_id: int = None):
    """Тест SearchAgentV2"""
    
    logger.info("=" * 100)
    logger.info("🚀 SEARCH AGENT V2 TEST (WITH WEB SCRAPING)")
    logger.info("=" * 100)
    
    # Получаем аккаунты
    accounts = get_all_accounts()
    logger.info(f"\n📋 Found {len(accounts)} accounts in database")
    
    # Показываем список с персонами
    logger.info("\nAccounts with personas:")
    accounts_with_persona = []
    for acc in accounts:
        persona = get_persona(acc['id'])
        if persona:
            accounts_with_persona.append((acc, persona))
            logger.info(
                f"  {acc['id']:3d}. {persona.get('generated_name'):25s} | "
                f"{persona.get('city'):20s} | Session: {acc['session_id'][:8]}"
            )
    
    if not accounts_with_persona:
        logger.error("❌ No accounts with personas found!")
        return
    
    # Выбираем аккаунт
    if account_id is None:
        # Берем первый аккаунт
        account, persona = accounts_with_persona[0]
        logger.info(f"\n🎯 Using first account: {account['id']} - {persona.get('generated_name')}")
    else:
        account = next((a for a, p in accounts_with_persona if a['id'] == account_id), None)
        if not account:
            logger.error(f"❌ Account {account_id} not found or has no persona!")
            return
        persona = get_persona(account_id)
    
    logger.info("\n" + "=" * 100)
    logger.info(f"🎯 Testing with account: {account['id']}")
    logger.info(f"   Name:        {persona.get('generated_name')}")
    logger.info(f"   City:        {persona.get('city')}")
    logger.info(f"   Interests:   {', '.join(persona.get('interests', []))}")
    logger.info(f"   Occupation:  {persona.get('occupation')}")
    logger.info(f"   Age:         {persona.get('age')}")
    logger.info("=" * 100)
    
    # Создаем SearchAgentV2
    search_agent = SearchAgentV2()
    
    try:
        # Запускаем поиск
        logger.info("\n🔍 Starting search with web scraping...")
        logger.info("=" * 100)
        
        start_time = datetime.now()
        
        channels = await search_agent.find_relevant_chats(
            persona,
            limit=settings.search_chats_per_persona
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Финальный отчет
        logger.info("\n" + "=" * 100)
        logger.info("📊 FINAL REPORT")
        logger.info("=" * 100)
        logger.info(f"\nSearch duration: {duration:.1f} seconds")
        logger.info(f"Channels found: {len(channels)}")
        
        if channels:
            logger.info("\n✅ Top 10 channels:")
            logger.info("=" * 100)
            for i, ch in enumerate(channels[:10], 1):
                logger.info(
                    f"{i:2d}. {ch['chat_username']:25s} | "
                    f"Score: {ch['relevance_score']:.2f} | "
                    f"Type: {ch['chat_type']:10s} | "
                    f"{ch['relevance_reason'][:50]}"
                )
            
            # Детали всех найденных каналов
            logger.info("\n📋 All found channels:")
            logger.info("=" * 100)
            for i, ch in enumerate(channels, 1):
                logger.info(f"\n{i}. {ch['chat_username']}")
                logger.info(f"   Title:       {ch.get('chat_title', 'N/A')}")
                logger.info(f"   Type:        {ch.get('chat_type', 'unknown')}")
                logger.info(f"   Score:       {ch['relevance_score']:.2f}")
                logger.info(f"   Reason:      {ch.get('relevance_reason', 'N/A')}")
                logger.info(f"   Description: {ch.get('chat_description', 'N/A')[:100]}")
        else:
            logger.warning("⚠️ No channels found!")
        
        # Сохраняем детальный отчет в JSON
        report = {
            "account_id": account['id'],
            "persona": {
                "name": persona.get('generated_name'),
                "city": persona.get('city'),
                "interests": persona.get('interests'),
                "occupation": persona.get('occupation'),
                "age": persona.get('age')
            },
            "search_duration_seconds": duration,
            "channels_found": len(channels),
            "channels": channels,
            "timestamp": datetime.now().isoformat()
        }
        
        report_file = f"logs/search_v2_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n💾 Detailed report saved to: {report_file}")
        logger.info(f"📄 Full log saved to: {log_file}")
        
    finally:
        # Закрываем HTTP клиент
        await search_agent.close()
    
    logger.info("\n" + "=" * 100)
    logger.info("✅ TEST COMPLETED")
    logger.info("=" * 100)


if __name__ == "__main__":
    # Можно передать ID аккаунта как аргумент
    import sys
    
    account_id = None
    if len(sys.argv) > 1:
        try:
            account_id = int(sys.argv[1])
        except ValueError:
            print(f"Invalid account ID: {sys.argv[1]}")
            sys.exit(1)
    
    asyncio.run(test_search_v2(account_id))




