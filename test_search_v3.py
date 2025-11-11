"""
Тест SearchAgentV3 (каталоги напрямую)
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

Path("logs").mkdir(exist_ok=True)

log_file = f'logs/search_v3_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

from database import get_all_accounts, get_persona
from search_agent_v3 import SearchAgentV3
from config import settings


async def test_search_v3(account_id: int = None):
    """Тест SearchAgentV3"""
    
    logger.info("=" * 100)
    logger.info("🚀 SEARCH AGENT V3 TEST (CATALOGS)")
    logger.info("=" * 100)
    
    # Получаем аккаунты
    accounts = get_all_accounts()
    accounts_with_persona = [(acc, get_persona(acc['id'])) for acc in accounts if get_persona(acc['id'])]
    
    if not accounts_with_persona:
        logger.error("❌ No accounts with personas found!")
        return
    
    # Выбираем аккаунт
    if account_id is None:
        account, persona = accounts_with_persona[0]
    else:
        account = next((a for a, p in accounts_with_persona if a['id'] == account_id), None)
        if not account:
            logger.error(f"❌ Account {account_id} not found!")
            return
        persona = get_persona(account_id)
    
    logger.info(f"\n🎯 Testing with account: {account['id']}")
    logger.info(f"   Name:        {persona.get('generated_name')}")
    logger.info(f"   City:        {persona.get('city')}")
    logger.info(f"   Interests:   {', '.join(persona.get('interests', [])[:3])}")
    
    # Создаем SearchAgentV3
    search_agent = SearchAgentV3()
    
    try:
        logger.info("\n🔍 Starting search via catalogs...")
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
            logger.info("\n✅ All channels:")
            logger.info("=" * 100)
            for i, ch in enumerate(channels, 1):
                logger.info(
                    f"{i:2d}. {ch['chat_username']:25s} | "
                    f"Score: {ch['relevance_score']:.2f} | "
                    f"Type: {ch['chat_type']:10s} | "
                    f"{ch['relevance_reason'][:50]}"
                )
        else:
            logger.warning("⚠️ No channels found!")
        
        logger.info(f"\n📄 Full log saved to: {log_file}")
        
    finally:
        await search_agent.close()
    
    logger.info("\n" + "=" * 100)
    logger.info("✅ TEST COMPLETED")
    logger.info("=" * 100)


if __name__ == "__main__":
    account_id = None
    if len(sys.argv) > 1:
        try:
            account_id = int(sys.argv[1])
        except ValueError:
            print(f"Invalid account ID: {sys.argv[1]}")
            sys.exit(1)
    
    asyncio.run(test_search_v3(account_id))




