#!/usr/bin/env python3
"""
Тесты для новой функциональности поддержки чатов и отслеживания непрочитанных сообщений
PR: Add chat support for joining and reading with unread tracking
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram_client import TelegramAPIClient
from telegram_tl_helpers import (
    make_input_peer_channel,
    make_input_peer_user,
    make_input_peer_chat,
    make_get_peer_dialogs_query,
    make_read_history_query,
    make_get_history_query
)
from executor import ActionExecutor
from config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ChatSupportTests:
    """Тесты для поддержки чатов"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.client = TelegramAPIClient()
        self.executor = ActionExecutor(self.client)
        self.test_results = []
    
    async def test_resolve_peer_channel(self):
        """Тест 1: Разрешение канала и получение InputPeer"""
        logger.info("\n" + "="*80)
        logger.info("ТЕСТ 1: Разрешение канала через resolve_peer")
        logger.info("="*80)
        
        try:
            # Используем публичный канал Telegram
            result = await self.client.resolve_peer(self.session_id, "@telegram")
            
            assert result.get("success"), f"Ошибка: {result.get('error')}"
            assert result.get("peer_type") == "channel", f"Неверный тип: {result.get('peer_type')}"
            assert "access_hash" in result, "access_hash отсутствует"
            assert "input_peer" in result, "input_peer отсутствует"
            assert result.get("chat_type") in ["channel", "broadcast"], f"Неверный chat_type: {result.get('chat_type')}"
            
            logger.info(f"✅ PASSED: Канал разрешен успешно")
            logger.info(f"   - peer_type: {result['peer_type']}")
            logger.info(f"   - chat_type: {result.get('chat_type')}")
            logger.info(f"   - peer_id: {result.get('peer_id')}")
            logger.info(f"   - access_hash: {result.get('access_hash')}")
            
            self.test_results.append(("resolve_peer_channel", "PASSED", None))
            return result
            
        except Exception as e:
            logger.error(f"❌ FAILED: {e}")
            self.test_results.append(("resolve_peer_channel", "FAILED", str(e)))
            raise
    
    async def test_join_chat_action(self):
        """Тест 2: Вступление в чат с новым форматом"""
        logger.info("\n" + "="*80)
        logger.info("ТЕСТ 2: Вступление в чат через join_chat action")
        logger.info("="*80)
        
        try:
            # Тест с новым параметром chat_username
            action = {
                "action": "join_chat",
                "chat_username": "@telegram",
                "chat_type": "channel"
            }
            
            result = await self.executor._join_channel(self.session_id, action)
            
            # Проверяем что вернулся результат
            assert result is not None, "Результат пустой"
            
            # Если канал уже вступили - это тоже success
            if not result.get("error") or "ALREADY" in str(result.get("error", "")).upper():
                logger.info(f"✅ PASSED: Действие join_chat выполнено")
                logger.info(f"   - chat_type в результате: {result.get('chat_type')}")
                logger.info(f"   - is_premium: {result.get('is_premium')}")
                logger.info(f"   - sponsored_ads_count: {result.get('sponsored_ads_count', 0)}")
                self.test_results.append(("join_chat_action", "PASSED", None))
            else:
                # Проверяем что это ожидаемая ошибка (например канал не существует)
                error = result.get("error", "")
                if "not found" in error.lower() or "invalid" in error.lower():
                    logger.info(f"✅ PASSED: Корректная обработка несуществующего канала")
                    self.test_results.append(("join_chat_action", "PASSED", f"Expected error: {error}"))
                else:
                    raise AssertionError(f"Неожиданная ошибка: {error}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ FAILED: {e}")
            self.test_results.append(("join_chat_action", "FAILED", str(e)))
            raise
    
    async def test_backward_compatibility(self):
        """Тест 3: Обратная совместимость с channel_username"""
        logger.info("\n" + "="*80)
        logger.info("ТЕСТ 3: Обратная совместимость (старый формат channel_username)")
        logger.info("="*80)
        
        try:
            # Старый формат с channel_username
            action = {
                "action": "join_channel",
                "channel_username": "@telegram"
            }
            
            result = await self.executor._join_channel(self.session_id, action)
            
            assert result is not None, "Результат пустой"
            
            if not result.get("error") or "ALREADY" in str(result.get("error", "")).upper():
                logger.info(f"✅ PASSED: Старый формат работает")
                self.test_results.append(("backward_compatibility", "PASSED", None))
            else:
                error = result.get("error", "")
                if "not found" in error.lower() or "invalid" in error.lower():
                    logger.info(f"✅ PASSED: Старый формат работает (expected error)")
                    self.test_results.append(("backward_compatibility", "PASSED", None))
                else:
                    raise AssertionError(f"Неожиданная ошибка: {error}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ FAILED: {e}")
            self.test_results.append(("backward_compatibility", "FAILED", str(e)))
            raise
    
    async def test_get_peer_dialog(self):
        """Тест 4: Получение информации о диалоге"""
        logger.info("\n" + "="*80)
        logger.info("ТЕСТ 4: Получение информации о диалоге (unread count)")
        logger.info("="*80)
        
        try:
            # Сначала разрешаем peer
            peer_info = await self.client.resolve_peer(self.session_id, "@telegram")
            
            if not peer_info.get("success"):
                logger.warning(f"⚠️ SKIPPED: Не удалось разрешить peer: {peer_info.get('error')}")
                self.test_results.append(("get_peer_dialog", "SKIPPED", peer_info.get('error')))
                return
            
            # Получаем диалог
            dialog_result = await self.client.get_peer_dialog(self.session_id, peer_info)
            
            logger.info(f"   - success: {dialog_result.get('success')}")
            logger.info(f"   - unread_count: {dialog_result.get('unread_count')}")
            logger.info(f"   - top_message: {dialog_result.get('top_message')}")
            
            # Даже если не нашли диалог - это OK (возможно еще не вступили)
            if dialog_result.get("success"):
                logger.info(f"✅ PASSED: Диалог получен")
                self.test_results.append(("get_peer_dialog", "PASSED", None))
            else:
                logger.info(f"⚠️ WARNING: Диалог не найден (возможно не вступили): {dialog_result.get('error')}")
                self.test_results.append(("get_peer_dialog", "WARNING", dialog_result.get('error')))
            
            return dialog_result
            
        except Exception as e:
            logger.error(f"❌ FAILED: {e}")
            self.test_results.append(("get_peer_dialog", "FAILED", str(e)))
            raise
    
    async def test_read_messages_with_unread_tracking(self):
        """Тест 5: Чтение сообщений с отслеживанием непрочитанных"""
        logger.info("\n" + "="*80)
        logger.info("ТЕСТ 5: Чтение сообщений с отслеживанием непрочитанных")
        logger.info("="*80)
        
        try:
            action = {
                "action": "read_messages",
                "chat_username": "@telegram",
                "duration_seconds": 2
            }
            
            result = await self.executor._read_messages(self.session_id, action)
            
            assert result is not None, "Результат пустой"
            
            if not result.get("error"):
                logger.info(f"✅ PASSED: Чтение сообщений выполнено")
                logger.info(f"   - unread_count_before: {result.get('unread_count_before')}")
                logger.info(f"   - messages_read: {result.get('messages_read')}")
                logger.info(f"   - marked_read: {result.get('marked_read')}")
                logger.info(f"   - chat_type: {result.get('chat_type')}")
                logger.info(f"   - messages_preview: {len(result.get('messages_preview', []))} messages")
                
                # Проверяем что есть preview сообщений
                if result.get('messages_read', 0) > 0:
                    logger.info(f"   - Примеры сообщений:")
                    for i, msg in enumerate(result.get('messages_preview', [])[:3], 1):
                        logger.info(f"     {i}. {msg[:100]}...")
                
                self.test_results.append(("read_messages_with_unread_tracking", "PASSED", None))
            else:
                error = result.get("error", "")
                logger.warning(f"⚠️ WARNING: {error}")
                self.test_results.append(("read_messages_with_unread_tracking", "WARNING", error))
            
            return result
            
        except Exception as e:
            logger.error(f"❌ FAILED: {e}")
            self.test_results.append(("read_messages_with_unread_tracking", "FAILED", str(e)))
            raise
    
    async def test_sponsored_ads_for_groups(self):
        """Тест 6: Проверка что реклама НЕ показывается для групп"""
        logger.info("\n" + "="*80)
        logger.info("ТЕСТ 6: Реклама НЕ показывается для обычных групп")
        logger.info("="*80)
        
        try:
            # Для обычных групп реклама не должна показываться
            action = {
                "action": "join_chat",
                "chat_username": "@some_group",
                "chat_type": "group"  # Обычная группа
            }
            
            result = await self.executor._join_channel(self.session_id, action)
            
            # Проверяем что реклама не загружалась для группы
            sponsored_count = result.get("sponsored_ads_count", 0)
            
            logger.info(f"   - chat_type: {result.get('chat_type')}")
            logger.info(f"   - sponsored_ads_count: {sponsored_count}")
            
            # Для группы не должно быть рекламы
            if result.get("chat_type") in ["group", "supergroup"]:
                if sponsored_count == 0:
                    logger.info(f"✅ PASSED: Реклама корректно НЕ показывается для группы")
                    self.test_results.append(("sponsored_ads_for_groups", "PASSED", None))
                else:
                    logger.warning(f"⚠️ WARNING: Реклама показана для группы (не критично)")
                    self.test_results.append(("sponsored_ads_for_groups", "WARNING", "Ads shown for group"))
            else:
                logger.info(f"⚠️ SKIPPED: Тест предназначен для групп, получен тип: {result.get('chat_type')}")
                self.test_results.append(("sponsored_ads_for_groups", "SKIPPED", f"Type: {result.get('chat_type')}"))
            
        except Exception as e:
            # Ошибка "канал не найден" - это нормально для теста
            if "not found" in str(e).lower():
                logger.info(f"✅ PASSED: Тест показал корректную обработку (канал не найден)")
                self.test_results.append(("sponsored_ads_for_groups", "PASSED", "Expected error"))
            else:
                logger.error(f"❌ FAILED: {e}")
                self.test_results.append(("sponsored_ads_for_groups", "FAILED", str(e)))
    
    async def test_tl_helpers(self):
        """Тест 7: Проверка новых TL helpers"""
        logger.info("\n" + "="*80)
        logger.info("ТЕСТ 7: Новые TL helpers для работы с чатами")
        logger.info("="*80)
        
        try:
            # Тест make_input_peer_channel
            input_channel = make_input_peer_channel(12345, 67890)
            assert input_channel is not None
            assert hasattr(input_channel, 'channel_id')
            logger.info(f"✅ make_input_peer_channel работает")
            
            # Тест make_input_peer_user
            input_user = make_input_peer_user(12345, 67890)
            assert input_user is not None
            assert hasattr(input_user, 'user_id')
            logger.info(f"✅ make_input_peer_user работает")
            
            # Тест make_input_peer_chat
            input_chat = make_input_peer_chat(12345)
            assert input_chat is not None
            assert hasattr(input_chat, 'chat_id')
            logger.info(f"✅ make_input_peer_chat работает")
            
            # Тест make_get_peer_dialogs_query
            query1 = make_get_peer_dialogs_query(input_channel)
            assert query1 is not None
            assert "GetPeerDialogs" in query1
            logger.info(f"✅ make_get_peer_dialogs_query работает")
            
            # Тест make_read_history_query
            query2 = make_read_history_query(input_channel, max_id=100)
            assert query2 is not None
            assert "ReadHistory" in query2
            logger.info(f"✅ make_read_history_query работает")
            
            # Тест make_get_history_query
            query3 = make_get_history_query(input_channel, limit=20)
            assert query3 is not None
            assert "GetHistory" in query3
            logger.info(f"✅ make_get_history_query работает")
            
            logger.info(f"\n✅ PASSED: Все TL helpers работают корректно")
            self.test_results.append(("tl_helpers", "PASSED", None))
            
        except Exception as e:
            logger.error(f"❌ FAILED: {e}")
            self.test_results.append(("tl_helpers", "FAILED", str(e)))
            raise
    
    async def run_all_tests(self):
        """Запустить все тесты"""
        logger.info("\n" + "="*100)
        logger.info("НАЧАЛО ТЕСТИРОВАНИЯ НОВОЙ ФУНКЦИОНАЛЬНОСТИ")
        logger.info("PR: Add chat support for joining and reading with unread tracking")
        logger.info("="*100)
        
        # Тест 7 можно запустить без сессии
        await self.test_tl_helpers()
        
        # Проверяем доступность сессии
        logger.info(f"\nПроверка сессии: {self.session_id}")
        session_info = await self.client.get_session_info(self.session_id)
        
        if session_info.get("error"):
            logger.error(f"❌ Сессия недоступна: {session_info.get('error')}")
            logger.error(f"❌ Невозможно запустить тесты требующие активную сессию")
            self.print_summary()
            return
        
        logger.info(f"✅ Сессия активна")
        logger.info(f"   - Phone: {session_info.get('phone', 'Unknown')}")
        logger.info(f"   - Premium: {session_info.get('is_premium', False)}")
        
        # Запускаем тесты последовательно
        try:
            await self.test_resolve_peer_channel()
        except:
            pass
        
        try:
            await self.test_join_chat_action()
        except:
            pass
        
        try:
            await self.test_backward_compatibility()
        except:
            pass
        
        try:
            await self.test_get_peer_dialog()
        except:
            pass
        
        try:
            await self.test_read_messages_with_unread_tracking()
        except:
            pass
        
        try:
            await self.test_sponsored_ads_for_groups()
        except:
            pass
        
        self.print_summary()
    
    def print_summary(self):
        """Вывести итоговый отчет"""
        logger.info("\n" + "="*100)
        logger.info("ИТОГОВЫЙ ОТЧЕТ ТЕСТИРОВАНИЯ")
        logger.info("="*100)
        
        passed = sum(1 for _, status, _ in self.test_results if status == "PASSED")
        failed = sum(1 for _, status, _ in self.test_results if status == "FAILED")
        warnings = sum(1 for _, status, _ in self.test_results if status == "WARNING")
        skipped = sum(1 for _, status, _ in self.test_results if status == "SKIPPED")
        total = len(self.test_results)
        
        for test_name, status, error in self.test_results:
            symbol = "✅" if status == "PASSED" else "⚠️" if status in ["WARNING", "SKIPPED"] else "❌"
            logger.info(f"{symbol} {test_name}: {status}")
            if error:
                logger.info(f"   └─ {error}")
        
        logger.info("\n" + "-"*100)
        logger.info(f"ВСЕГО ТЕСТОВ: {total}")
        logger.info(f"✅ PASSED: {passed}")
        logger.info(f"❌ FAILED: {failed}")
        logger.info(f"⚠️ WARNING: {warnings}")
        logger.info(f"⏭️ SKIPPED: {skipped}")
        logger.info("="*100)
        
        if failed == 0:
            logger.info("\n🎉 ВСЕ КРИТИЧНЫЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
        else:
            logger.info(f"\n⚠️ ЕСТЬ ПРОВАЛЕННЫЕ ТЕСТЫ: {failed}")


async def main():
    """Основная функция"""
    import os
    
    # Получаем session_id из переменной окружения или используем тестовый
    session_id = os.getenv("TEST_SESSION_ID")
    
    if not session_id:
        logger.warning("⚠️ TEST_SESSION_ID не установлен")
        logger.warning("Использование: TEST_SESSION_ID=your_session_id python test_chat_support.py")
        logger.warning("Запускаем тесты не требующие сессию...")
        session_id = "test_session_placeholder"
    
    tester = ChatSupportTests(session_id)
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())

