"""
Тестовый скрипт для проверки чтения каналов как реальный пользователь

Этот скрипт:
1. Получает список каналов, на которые подписана сессия
2. Сравнивает с данными из базы
3. Читает каналы начиная с первого непрочитанного сообщения
4. Помечает сообщения как прочитанные
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import random

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram_client import TelegramAPIClient
from database import get_db_connection
from config import settings

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Убираем DEBUG для httpx чтобы не засорять лог
logging.getLogger('httpx').setLevel(logging.WARNING)


class ChannelReader:
    """Класс для чтения каналов как реальный пользователь"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.telegram_client = TelegramAPIClient()
        
    async def get_subscribed_channels_from_db(self) -> List[Dict[str, Any]]:
        """Получить список каналов из базы данных для этой сессии"""
        
        logger.info(f"📊 Получаем список каналов из БД для сессии {self.session_id}")
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем account_id
            cursor.execute("""
                SELECT id FROM accounts WHERE session_id = ?
            """, (self.session_id,))
            
            account_row = cursor.fetchone()
            if not account_row:
                logger.warning(f"❌ Аккаунт с session_id {self.session_id} не найден в БД")
                return []
            
            account_id = account_row['id']
            
            # Получаем каналы, помеченные как is_joined
            cursor.execute("""
                SELECT 
                    chat_username,
                    chat_title,
                    chat_type,
                    is_joined,
                    joined_at,
                    relevance_score,
                    relevance_reason
                FROM discovered_chats
                WHERE account_id = ? AND is_joined = 1
                ORDER BY joined_at DESC
            """, (account_id,))
            
            channels = []
            for row in cursor.fetchall():
                channels.append({
                    'username': row['chat_username'],
                    'title': row['chat_title'],
                    'chat_type': row['chat_type'],
                    'joined_at': row['joined_at'],
                    'relevance_score': row['relevance_score'],
                    'relevance_reason': row['relevance_reason']
                })
            
            logger.info(f"✅ Найдено {len(channels)} каналов в БД (is_joined=1)")
            return channels
    
    async def get_all_dialogs(self) -> List[Dict[str, Any]]:
        """Получить все диалоги (каналы) из Telegram API"""
        
        logger.info(f"📡 Получаем список диалогов из Telegram API для сессии {self.session_id}")
        
        all_dialogs = []
        limit = 100
        offset_date = 0
        offset_id = 0
        
        # Получаем диалоги партиями
        for iteration in range(5):  # Максимум 5 итераций = 500 диалогов
            logger.info(f"  📥 Получаем диалоги (итерация {iteration + 1}, offset_id={offset_id})")
            
            dialogs_result = await self.telegram_client.get_dialogs(
                self.session_id,
                limit=limit
            )
            
            if dialogs_result.get('error'):
                logger.error(f"❌ Ошибка получения диалогов: {dialogs_result.get('error')}")
                break
            
            result = dialogs_result.get('result', {})
            dialogs = result.get('dialogs', [])
            
            if not dialogs:
                logger.info("  ℹ️ Больше диалогов нет")
                break
            
            logger.info(f"  ✅ Получено {len(dialogs)} диалогов")
            all_dialogs.extend(dialogs)
            
            # Получаем offset для следующей итерации
            last_dialog = dialogs[-1]
            offset_id = last_dialog.get('top_message', 0)
            offset_date = 0  # Будет вычислен автоматически
            
            # Если получили меньше чем limit, значит это последняя страница
            if len(dialogs) < limit:
                break
        
        logger.info(f"✅ Всего получено {len(all_dialogs)} диалогов")
        
        # Фильтруем только каналы (не личные чаты, не боты)
        channels = []
        for dialog in all_dialogs:
            peer = dialog.get('peer', {})
            peer_type = peer.get('_', '')
            
            # Нас интересуют только каналы (PeerChannel)
            if 'PeerChannel' in peer_type:
                channels.append(dialog)
        
        logger.info(f"📺 Из них {len(channels)} каналов (PeerChannel)")
        
        return channels
    
    async def get_channel_info(self, dialog: Dict[str, Any], result_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Извлечь информацию о канале из диалога"""
        
        peer = dialog.get('peer', {})
        channel_id = peer.get('channel_id')
        
        if not channel_id:
            return None
        
        # Найти данные канала в результате
        chats = result_data.get('chats', [])
        channel_data = None
        
        for chat in chats:
            if chat.get('id') == channel_id:
                channel_data = chat
                break
        
        if not channel_data:
            return None
        
        username = channel_data.get('username', '')
        title = channel_data.get('title', 'Unknown')
        
        # Определить тип
        chat_type = 'channel'
        if channel_data.get('megagroup'):
            chat_type = 'supergroup'
        elif channel_data.get('broadcast'):
            chat_type = 'channel'
        
        unread_count = dialog.get('unread_count', 0)
        top_message = dialog.get('top_message', 0)
        read_inbox_max_id = dialog.get('read_inbox_max_id', 0)
        
        return {
            'channel_id': channel_id,
            'access_hash': channel_data.get('access_hash'),
            'username': f"@{username}" if username else f"channel_{channel_id}",
            'title': title,
            'chat_type': chat_type,
            'unread_count': unread_count,
            'top_message': top_message,
            'read_inbox_max_id': read_inbox_max_id,
            'dialog': dialog,
            'channel_data': channel_data
        }
    
    async def compare_channels(self, db_channels: List[Dict[str, Any]], telegram_channels: List[Dict[str, Any]]):
        """Сравнить каналы из БД и из Telegram"""
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 СРАВНЕНИЕ КАНАЛОВ ИЗ БД И TELEGRAM")
        logger.info("=" * 80)
        
        # Создать множества username'ов
        db_usernames = {ch['username'].lower() for ch in db_channels if ch['username']}
        telegram_usernames = {ch['username'].lower() for ch in telegram_channels if ch['username']}
        
        # В БД есть, но нет в Telegram (покинул канал или ошибка в БД)
        only_in_db = db_usernames - telegram_usernames
        
        # В Telegram есть, но нет в БД (вступил, но не отслеживается)
        only_in_telegram = telegram_usernames - db_usernames
        
        # В обоих
        in_both = db_usernames & telegram_usernames
        
        logger.info(f"✅ В БД и в Telegram: {len(in_both)} каналов")
        logger.info(f"⚠️ Только в БД (возможно покинул): {len(only_in_db)} каналов")
        logger.info(f"ℹ️ Только в Telegram (не отслеживается): {len(only_in_telegram)} каналов")
        
        if only_in_db:
            logger.info("")
            logger.info("⚠️ Каналы только в БД (возможно покинул):")
            for username in sorted(only_in_db)[:10]:  # Показываем первые 10
                ch = next(c for c in db_channels if c['username'].lower() == username)
                logger.info(f"  - {ch['username']}: {ch['title']}")
            
            if len(only_in_db) > 10:
                logger.info(f"  ... и еще {len(only_in_db) - 10} каналов")
        
        if only_in_telegram:
            logger.info("")
            logger.info("ℹ️ Каналы только в Telegram (не отслеживается в БД):")
            for username in sorted(only_in_telegram)[:10]:
                ch = next(c for c in telegram_channels if c['username'].lower() == username)
                unread = ch.get('unread_count', 0)
                logger.info(f"  - {ch['username']}: {ch['title']} (непрочитанных: {unread})")
            
            if len(only_in_telegram) > 10:
                logger.info(f"  ... и еще {len(only_in_telegram) - 10} каналов")
        
        logger.info("=" * 80)
        logger.info("")
    
    async def read_channel_messages(self, channel_info: Dict[str, Any], max_messages: int = 50) -> Dict[str, Any]:
        """
        Прочитать сообщения из канала как реальный пользователь
        
        Читаем с первого непрочитанного (read_inbox_max_id + 1) до последнего (top_message)
        Как в настоящем клиенте - скролл встает на первое непрочитанное и читаешь до конца
        """
        
        username = channel_info['username']
        unread_count = channel_info['unread_count']
        top_message = channel_info['top_message']
        read_inbox_max_id = channel_info['read_inbox_max_id']
        
        logger.info("")
        logger.info("-" * 80)
        logger.info(f"📖 Читаем канал: {username}")
        logger.info(f"   Название: {channel_info['title']}")
        logger.info(f"   Непрочитанных: {unread_count}")
        logger.info(f"   Последнее прочитанное: #{read_inbox_max_id}")
        logger.info(f"   Первое непрочитанное: #{read_inbox_max_id + 1}")
        logger.info(f"   Последнее сообщение: #{top_message}")
        logger.info("-" * 80)
        
        if unread_count == 0:
            logger.info("✅ Все сообщения уже прочитаны")
            return {
                'success': True,
                'messages_read': 0,
                'already_read': True
            }
        
        # Сначала нужно resolve канал, чтобы получить peer_info
        peer_info = await self.telegram_client.resolve_peer(self.session_id, username)
        
        if not peer_info.get('success'):
            logger.error(f"❌ Не удалось resolve канал: {peer_info.get('error')}")
            return {
                'success': False,
                'error': peer_info.get('error')
            }
        
        logger.info(f"✅ Канал resolved: {peer_info.get('peer_type')} (ID: {peer_info.get('peer_id')})")
        
        # Получаем информацию о диалоге (для проверки unread_count)
        dialog_info = await self.telegram_client.get_peer_dialog(self.session_id, peer_info)
        
        if dialog_info.get('success'):
            current_unread = dialog_info.get('unread_count', 0)
            logger.info(f"📊 Текущее количество непрочитанных: {current_unread}")
        
        # ПРАВИЛЬНЫЙ СПОСОБ: читаем с первого непрочитанного до последнего
        # Ограничиваем максимальным количеством для безопасности
        messages_to_read = min(unread_count, max_messages)
        
        # Используем offset_id = первое непрочитанное, чтобы начать с него
        first_unread_id = read_inbox_max_id + 1
        
        logger.info(f"📥 Читаем непрочитанные сообщения (с #{first_unread_id} до #{top_message})...")
        logger.info(f"   Запрашиваем до {messages_to_read} сообщений")
        
        # Получаем сообщения начиная с первого непрочитанного
        # offset_id - начинаем с этого сообщения (первое непрочитанное)
        # add_offset = 0 - берем это сообщение и следующие
        # limit - сколько взять
        from telegram_tl_helpers import make_get_history_query
        
        query = make_get_history_query(
            peer=peer_info['input_peer'],
            offset_id=first_unread_id,  # Начинаем с первого непрочитанного
            add_offset=0,  # Берем включая это сообщение
            limit=messages_to_read
        )
        
        history_result = await self.telegram_client.invoke_raw(self.session_id, query)
        
        if history_result.get('error'):
            logger.error(f"❌ Ошибка получения истории: {history_result.get('error')}")
            return {
                'success': False,
                'error': history_result.get('error')
            }
        
        # Извлекаем сообщения
        result = history_result.get('result', {})
        messages = result.get('messages', [])
        
        if not messages:
            logger.warning("⚠️ Сообщений не получено")
            return {
                'success': True,
                'messages_read': 0,
                'no_messages': True
            }
        
        # Сортируем сообщения по ID (от старых к новым), т.к. API возвращает от новых к старым
        messages_sorted = sorted(messages, key=lambda m: m.get('id', 0))
        
        logger.info(f"✅ Получено {len(messages_sorted)} непрочитанных сообщений")
        logger.info(f"   Диапазон: #{messages_sorted[0].get('id')} - #{messages_sorted[-1].get('id')}")
        
        # Показываем несколько сообщений (от старых к новым, как читает человек)
        logger.info("")
        logger.info("📝 Непрочитанные сообщения (от старых к новым):")
        for i, msg in enumerate(messages_sorted[:5]):  # Показываем первые 5
            msg_id = msg.get('id', 0)
            msg_text = msg.get('message', '')
            msg_date = msg.get('date', 0)
            
            # Конвертируем timestamp в datetime
            if msg_date:
                msg_datetime = datetime.fromtimestamp(msg_date)
                date_str = msg_datetime.strftime('%Y-%m-%d %H:%M:%S')
            else:
                date_str = 'unknown'
            
            # Обрезаем текст
            text_preview = msg_text[:60] + '...' if len(msg_text) > 60 else msg_text
            text_preview = text_preview.replace('\n', ' ')
            
            logger.info(f"   #{msg_id} [{date_str}]: {text_preview}")
        
        if len(messages_sorted) > 5:
            logger.info(f"   ...")
            # Показываем последние 2 (самые свежие)
            for msg in messages_sorted[-2:]:
                msg_id = msg.get('id', 0)
                msg_text = msg.get('message', '')
                msg_date = msg.get('date', 0)
                
                if msg_date:
                    msg_datetime = datetime.fromtimestamp(msg_date)
                    date_str = msg_datetime.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    date_str = 'unknown'
                
                text_preview = msg_text[:60] + '...' if len(msg_text) > 60 else msg_text
                text_preview = text_preview.replace('\n', ' ')
                
                logger.info(f"   #{msg_id} [{date_str}]: {text_preview}")
        
        # Имитируем время чтения (как настоящий человек)
        # Время зависит от длины текста сообщения
        logger.info(f"")
        logger.info(f"⏳ Читаем сообщения...")
        
        total_read_time = 0.0
        skip_probability = 0.15 if len(messages_sorted) >= 3 else 0  # 15% шанс пролистать если 3+ сообщений
        
        for i, msg in enumerate(messages_sorted):
            msg_text = msg.get('message', '')
            text_length = len(msg_text)
            
            # Некоторые сообщения пролистываются быстро (не вникая)
            if random.random() < skip_probability:
                # Быстрый скролл - 0.3-0.8 сек
                msg_read_time = random.uniform(0.3, 0.8)
                if i % 10 == 0:  # Логируем каждое 10-е для краткости
                    logger.debug(f"   Сообщение #{msg.get('id')} пролистано быстро ({msg_read_time:.1f}с)")
            else:
                # Реальное чтение: ~200-300 символов в минуту = ~3-5 символов в секунду
                # Плюс 1-2 секунды на "осмысление"
                base_time = 1.0  # Минимальное время на любое сообщение
                reading_speed = random.uniform(3, 6)  # символов в секунду
                reading_time = text_length / reading_speed
                thinking_time = random.uniform(0.5, 2.0)  # Время на осмысление
                
                msg_read_time = base_time + reading_time + thinking_time
                
                # Ограничиваем максимум (очень длинные сообщения не читают до конца)
                msg_read_time = min(msg_read_time, 30.0)
                
                if i < 3 or i % 10 == 0:  # Логируем первые 3 и каждое 10-е
                    logger.debug(f"   Сообщение #{msg.get('id')} ({text_length} симв.): {msg_read_time:.1f}с")
            
            total_read_time += msg_read_time
            await asyncio.sleep(msg_read_time)
        
        logger.info(f"✅ Прочитано за {total_read_time:.1f} сек (среднее {total_read_time/len(messages_sorted):.1f}с/сообщение)")
        
        # Помечаем сообщения как прочитанные
        # Берем ID самого нового сообщения (последнее в отсортированном списке)
        max_msg_id = messages_sorted[-1].get('id', 0)
        
        if max_msg_id > 0:
            logger.info(f"✅ Помечаем сообщения до #{max_msg_id} как прочитанные...")
            
            mark_result = await self.telegram_client.mark_history_read(
                self.session_id,
                peer_info,
                max_id=max_msg_id
            )
            
            if mark_result.get('error'):
                logger.warning(f"⚠️ Не удалось пометить как прочитанное: {mark_result.get('error')}")
                marked_read = False
            else:
                logger.info(f"✅ Сообщения помечены как прочитанные")
                marked_read = True
        else:
            logger.warning("⚠️ Не удалось определить max_msg_id")
            marked_read = False
        
        return {
            'success': True,
            'messages_read': len(messages_sorted),
            'first_msg_id': messages_sorted[0].get('id', 0),
            'last_msg_id': max_msg_id,
            'marked_read': marked_read,
            'messages': messages_sorted[:5]  # Возвращаем первые 5 для логов
        }
    
    async def run_test(self, max_channels_to_read: int = 5):
        """Запустить тест чтения каналов"""
        
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"🚀 ТЕСТ ЧТЕНИЯ КАНАЛОВ ДЛЯ СЕССИИ {self.session_id}")
        logger.info("=" * 80)
        logger.info("")
        
        # 1. Получить каналы из БД
        db_channels = await self.get_subscribed_channels_from_db()
        
        # 2. Получить все диалоги из Telegram
        telegram_dialogs = await self.get_all_dialogs()
        
        # 3. Извлечь информацию о каналах
        logger.info("")
        logger.info("📊 Извлекаем информацию о каналах...")
        
        # Получаем результат с chats для резолва username'ов
        dialogs_result = await self.telegram_client.get_dialogs(self.session_id, limit=100)
        result_data = dialogs_result.get('result', {})
        
        telegram_channels = []
        for dialog in telegram_dialogs:
            channel_info = await self.get_channel_info(dialog, result_data)
            if channel_info:
                telegram_channels.append(channel_info)
        
        logger.info(f"✅ Извлечено {len(telegram_channels)} каналов с полной информацией")
        
        # 4. Сравнить каналы
        await self.compare_channels(db_channels, telegram_channels)
        
        # 5. Найти каналы с непрочитанными сообщениями
        channels_with_unread = [
            ch for ch in telegram_channels 
            if ch.get('unread_count', 0) > 0
        ]
        
        # Сортируем по количеству непрочитанных (сначала меньше)
        channels_with_unread.sort(key=lambda x: x.get('unread_count', 0))
        
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"📬 КАНАЛЫ С НЕПРОЧИТАННЫМИ СООБЩЕНИЯМИ: {len(channels_with_unread)}")
        logger.info("=" * 80)
        
        if not channels_with_unread:
            logger.info("✅ Все каналы прочитаны!")
            return
        
        # Показываем первые 10
        logger.info("")
        logger.info("Топ-10 каналов с непрочитанными:")
        for i, ch in enumerate(channels_with_unread[:10]):
            logger.info(
                f"  {i+1}. {ch['username']}: {ch['title'][:40]} "
                f"(непрочитанных: {ch['unread_count']})"
            )
        
        if len(channels_with_unread) > 10:
            logger.info(f"  ... и еще {len(channels_with_unread) - 10} каналов")
        
        # 6. Читаем каналы
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"📖 НАЧИНАЕМ ЧТЕНИЕ КАНАЛОВ (максимум {max_channels_to_read})")
        logger.info("=" * 80)
        
        channels_to_read = channels_with_unread[:max_channels_to_read]
        
        read_summary = {
            'total_channels': len(channels_to_read),
            'successfully_read': 0,
            'failed': 0,
            'total_messages': 0
        }
        
        for i, channel in enumerate(channels_to_read):
            logger.info(f"\n📖 [{i+1}/{len(channels_to_read)}] Читаем канал...")
            
            result = await self.read_channel_messages(channel, max_messages=50)
            
            if result.get('success'):
                read_summary['successfully_read'] += 1
                read_summary['total_messages'] += result.get('messages_read', 0)
            else:
                read_summary['failed'] += 1
            
            # Пауза между каналами (как настоящий человек)
            if i < len(channels_to_read) - 1:
                pause = random.uniform(3, 7)
                logger.info(f"⏸️ Пауза {pause:.1f} сек перед следующим каналом...")
                await asyncio.sleep(pause)
        
        # 7. Итоги
        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 ИТОГИ ЧТЕНИЯ КАНАЛОВ")
        logger.info("=" * 80)
        logger.info(f"✅ Успешно прочитано: {read_summary['successfully_read']} каналов")
        logger.info(f"❌ Ошибки: {read_summary['failed']} каналов")
        logger.info(f"📝 Всего прочитано сообщений: {read_summary['total_messages']}")
        logger.info(f"📺 Осталось каналов с непрочитанными: {len(channels_with_unread) - len(channels_to_read)}")
        logger.info("=" * 80)
        
        # Закрываем клиент
        await self.telegram_client.close()


async def main():
    """Главная функция"""
    
    # ID сессии для тестирования
    session_id = "27067"
    
    # Создаем ридер
    reader = ChannelReader(session_id)
    
    # Запускаем тест
    # max_channels_to_read - сколько каналов максимум прочитать
    await reader.run_test(max_channels_to_read=5)


if __name__ == "__main__":
    asyncio.run(main())

