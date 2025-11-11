#!/usr/bin/env python3
"""
Тестовый скрипт для проверки получения country из Admin API
для активных сессий из базы прогрева
"""

import asyncio
import sys
import logging
sys.path.insert(0, '.')

from database import get_accounts_for_warmup
from admin_api_client import AdminAPIClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_session_country():
    """Тестирует получение country из Admin API для активных сессий"""
    
    # Получаем активные сессии из базы
    logger.info("Получаю активные сессии из базы прогрева...")
    accounts = get_accounts_for_warmup()
    
    if not accounts:
        logger.warning("❌ Нет активных сессий в базе прогрева")
        return
    
    logger.info(f"✅ Найдено {len(accounts)} активных сессий")
    
    # Берем первую сессию для теста
    test_account = accounts[0]
    session_id = test_account.get('session_id')
    
    logger.info(f"\n{'='*80}")
    logger.info(f"Тестирую сессию: {session_id}")
    logger.info(f"Account ID: {test_account.get('id')}")
    logger.info(f"Phone: {test_account.get('phone_number')}")
    logger.info(f"Country в локальной БД: {test_account.get('country')}")
    logger.info(f"{'='*80}\n")
    
    # Инициализируем клиент Admin API
    client = AdminAPIClient()
    
    try:
        # Пытаемся получить session_id как число
        try:
            session_id_int = int(session_id)
        except ValueError:
            logger.error(f"❌ Session ID '{session_id}' не является числом, пропускаю")
            return
        
        # Получаем данные сессии из Admin API
        logger.info(f"Запрашиваю данные сессии из Admin API...")
        session_data = await client.get_session_by_id(session_id_int)
        
        if not session_data:
            logger.warning(f"⚠️ Сессия {session_id} не найдена в Admin API")
            return
        
        # Проверяем наличие поля country
        country = session_data.get('country')
        
        logger.info(f"\n{'='*80}")
        logger.info("РЕЗУЛЬТАТЫ:")
        logger.info(f"{'='*80}")
        logger.info(f"Session ID: {session_id}")
        logger.info(f"Phone Number: {session_data.get('phone_number')}")
        logger.info(f"Country из Admin API: {country}")
        logger.info(f"Country в локальной БД: {test_account.get('country')}")
        
        if country:
            logger.info(f"✅ Country успешно получен из Admin API: '{country}'")
        else:
            logger.warning(f"⚠️ Country отсутствует или равен None в ответе Admin API")
        
        # Показываем все поля сессии для отладки
        logger.info(f"\nВсе поля сессии из Admin API:")
        for key, value in session_data.items():
            logger.info(f"  {key}: {value}")
        
        logger.info(f"{'='*80}\n")
        
        # Тестируем еще несколько сессий для полноты
        logger.info(f"\nТестирую еще несколько сессий...")
        tested_count = 0
        success_count = 0
        
        for account in accounts[1:6]:  # Берем еще 5 сессий
            try:
                sid = account.get('session_id')
                sid_int = int(sid)
                session = await client.get_session_by_id(sid_int)
                
                if session:
                    tested_count += 1
                    country_val = session.get('country')
                    if country_val:
                        success_count += 1
                        logger.info(f"  ✅ {sid}: country = '{country_val}'")
                    else:
                        logger.info(f"  ⚠️  {sid}: country = None")
                else:
                    logger.info(f"  ❌ {sid}: не найдена в Admin API")
            except (ValueError, Exception) as e:
                logger.info(f"  ❌ {account.get('session_id')}: ошибка - {e}")
        
        logger.info(f"\nИтого протестировано: {tested_count} сессий")
        logger.info(f"С country: {success_count} сессий")
        logger.info(f"Без country: {tested_count - success_count} сессий")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении данных из Admin API: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_session_country())

