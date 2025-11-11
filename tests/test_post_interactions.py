"""
Тестовый скрипт для проверки взаимодействия с постами в каналах

Этот скрипт:
1. Читает непрочитанные сообщения в каналах
2. С вероятностью 10% пересылает пост в избранное (Saved Messages)
3. Если у поста есть реакции, с вероятностью 15% ставит одну из существующих реакций
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import random

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram_client import TelegramAPIClient
from telegram_tl_helpers import make_get_history_query, raw_method_to_string
from database import get_db_connection
from config import settings
import pylogram.raw.types
import pylogram.raw.functions

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Убираем DEBUG для httpx
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('telegram_client').setLevel(logging.INFO)


class PostInteractionTester:
    """Класс для тестирования взаимодействия с постами"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.telegram_client = TelegramAPIClient()
        self.forwarded_posts = []  # Список пересланных постов
        self.reacted_posts = []    # Список постов с реакциями
        
    async def get_channels_with_unread(self, test_mode: bool = False) -> List[Dict[str, Any]]:
        """Получить каналы с непрочитанными сообщениями (или все в тестовом режиме)"""
        
        mode_text = "все каналы (тестовый режим)" if test_mode else "каналы с непрочитанными"
        logger.info(f"📊 Получаем {mode_text} для сессии {self.session_id}")
        
        # Получаем диалоги
        dialogs_result = await self.telegram_client.get_dialogs(self.session_id, limit=100)
        
        if dialogs_result.get('error'):
            logger.error(f"❌ Ошибка получения диалогов: {dialogs_result['error']}")
            return []
        
        result_data = dialogs_result.get('result', {})
        dialogs = result_data.get('dialogs', [])
        chats = {c['id']: c for c in result_data.get('chats', [])}
        
        logger.info(f"🔍 Всего диалогов: {len(dialogs)}, чатов: {len(chats)}")
        
        channels = []
        for dialog in dialogs:
            peer = dialog.get('peer', {})
            peer_id = peer.get('channel_id')
            
            if not peer_id:
                continue
                
            chat = chats.get(peer_id)
            if not chat:
                continue
            
            chat_type = chat.get('_')
            username = chat.get('username')
            title = chat.get('title', 'Unknown')
            
            # Проверяем что это канал (тип может быть 'Channel', 'ChannelForbidden', 'types.Channel', etc)
            if 'Channel' not in str(chat_type):
                logger.debug(f"   Пропускаем {title} (@{username}): тип {chat_type}")
                continue
            
            unread_count = dialog.get('unread_count', 0)
            top_message = dialog.get('top_message', 0)
            
            # В тестовом режиме берем каналы даже если нет непрочитанных
            if not test_mode and unread_count == 0:
                continue
            
            # В тестовом режиме если нет непрочитанных, читаем последние 20
            if test_mode and unread_count == 0:
                unread_count = min(20, top_message)
            
            channels.append({
                'id': peer_id,
                'username': username,
                'title': title,
                'unread_count': unread_count,
                'read_inbox_max_id': dialog.get('read_inbox_max_id', 0),
                'top_message': top_message,
                'access_hash': chat.get('access_hash'),
                'test_mode': test_mode and dialog.get('unread_count', 0) == 0
            })
        
        logger.info(f"✅ Найдено {len(channels)} каналов")
        return channels
    
    async def forward_to_saved(self, channel_id: int, message_id: int, channel_access_hash: int) -> bool:
        """Переслать сообщение в избранное (Saved Messages)"""
        
        try:
            # Получаем информацию о текущем пользователе
            me_result = await self.telegram_client.invoke_raw(
                self.session_id,
                raw_method_to_string(pylogram.raw.functions.users.GetFullUser(
                    id=pylogram.raw.types.InputUserSelf()
                ))
            )
            
            if me_result.get('error'):
                logger.error(f"❌ Не удалось получить информацию о пользователе: {me_result['error']}")
                return False
            
            # Пересылаем сообщение себе
            from_peer = pylogram.raw.types.InputPeerChannel(
                channel_id=channel_id,
                access_hash=channel_access_hash
            )
            
            to_peer = pylogram.raw.types.InputPeerSelf()
            
            forward_query = pylogram.raw.functions.messages.ForwardMessages(
                from_peer=from_peer,
                id=[message_id],
                to_peer=to_peer,
                random_id=[random.randint(1, 2**63 - 1)]
            )
            
            result = await self.telegram_client.invoke_raw(
                self.session_id,
                raw_method_to_string(forward_query)
            )
            
            if result.get('error'):
                logger.error(f"❌ Ошибка пересылки: {result['error']}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Исключение при пересылке: {e}")
            return False
    
    async def send_reaction(self, channel_id: int, message_id: int, 
                           channel_access_hash: int, emoji: str) -> bool:
        """Поставить реакцию на сообщение"""
        
        try:
            peer = pylogram.raw.types.InputPeerChannel(
                channel_id=channel_id,
                access_hash=channel_access_hash
            )
            
            # Создаем реакцию (эмодзи)
            reaction = pylogram.raw.types.ReactionEmoji(emoticon=emoji)
            
            reaction_query = pylogram.raw.functions.messages.SendReaction(
                peer=peer,
                msg_id=message_id,
                reaction=[reaction]
            )
            
            result = await self.telegram_client.invoke_raw(
                self.session_id,
                raw_method_to_string(reaction_query)
            )
            
            if result.get('error'):
                logger.error(f"❌ Ошибка отправки реакции: {result['error']}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Исключение при отправке реакции: {e}")
            return False
    
    def extract_reactions(self, message: Dict[str, Any]) -> List[str]:
        """Извлечь список эмодзи реакций из сообщения"""
        
        reactions_data = message.get('reactions')
        if not reactions_data:
            return []
        
        results = reactions_data.get('results', [])
        if not results:
            return []
        
        emojis = []
        for result in results:
            reaction = result.get('reaction', {})
            if reaction.get('_') == 'ReactionEmoji':
                emoji = reaction.get('emoticon')
                if emoji:
                    emojis.append(emoji)
        
        return emojis
    
    async def read_channel_with_interactions(self, channel: Dict[str, Any], 
                                            max_messages: int = 20) -> Dict[str, Any]:
        """Прочитать канал с возможными взаимодействиями"""
        
        channel_id = channel['id']
        username = channel.get('username', 'unknown')
        title = channel['title']
        unread_count = channel['unread_count']
        read_inbox_max_id = channel['read_inbox_max_id']
        top_message_id = channel['top_message']
        access_hash = channel['access_hash']
        is_test_mode = channel.get('test_mode', False)
        
        logger.info(f"")
        logger.info(f"📖 Канал: @{username} ({title})")
        
        if is_test_mode:
            logger.info(f"   🧪 Тестовый режим: читаем последние {unread_count} сообщений")
        else:
            logger.info(f"   Непрочитанных: {unread_count}")
        
        if unread_count == 0:
            logger.info(f"✅ Нечего читать")
            return {'forwarded': 0, 'reacted': 0}
        
        # Ограничиваем количество для теста
        messages_to_read = min(unread_count, max_messages)
        
        # Создаем peer
        peer = pylogram.raw.types.InputPeerChannel(
            channel_id=channel_id,
            access_hash=access_hash
        )
        
        # Получаем сообщения
        if is_test_mode:
            # В тестовом режиме читаем последние N сообщений
            logger.info(f"   Читаем последние {messages_to_read} сообщений")
            query = make_get_history_query(
                peer=peer,
                offset_id=0,  # 0 означает начать с самых новых
                add_offset=0,
                limit=messages_to_read
            )
        else:
            # В обычном режиме читаем с первого непрочитанного
            first_unread_id = read_inbox_max_id + 1
            logger.info(f"   Читаем {messages_to_read} сообщений начиная с #{first_unread_id}")
            query = make_get_history_query(
                peer=peer,
                offset_id=first_unread_id,
                add_offset=0,
                limit=messages_to_read
            )
        
        history_result = await self.telegram_client.invoke_raw(self.session_id, query)
        
        if history_result.get('error'):
            logger.error(f"❌ Ошибка получения истории: {history_result['error']}")
            return {'forwarded': 0, 'reacted': 0}
        
        result_data = history_result.get('result', {})
        messages = result_data.get('messages', [])
        
        # Сортируем от старых к новым
        messages_sorted = sorted(messages, key=lambda m: m.get('id', 0))
        
        logger.info(f"📥 Получено {len(messages_sorted)} сообщений")
        if messages_sorted:
            logger.info(f"   Диапазон: #{messages_sorted[0].get('id')} - #{messages_sorted[-1].get('id')}")
        
        forwarded_count = 0
        reacted_count = 0
        
        # Вероятности
        FORWARD_PROBABILITY = 0.10  # 10% шанс переслать
        REACTION_PROBABILITY = 0.15  # 15% шанс поставить реакцию
        
        for i, msg in enumerate(messages_sorted):
            msg_id = msg.get('id')
            msg_text = msg.get('message', '')
            text_length = len(msg_text)
            
            # Имитируем чтение
            reading_time = random.uniform(1.0, 3.0)
            if text_length > 100:
                reading_time = random.uniform(3.0, 8.0)
            
            # Получаем реакции
            existing_reactions = self.extract_reactions(msg)
            
            if i < 3:  # Логируем первые 3
                logger.info(f"   📬 Msg #{msg_id} ({text_length} симв.)")
                if existing_reactions:
                    logger.info(f"      Реакции: {', '.join(existing_reactions)}")
            
            # Пересылка в избранное
            if random.random() < FORWARD_PROBABILITY:
                logger.info(f"   💾 Пересылаем #{msg_id} в избранное...")
                if await self.forward_to_saved(channel_id, msg_id, access_hash):
                    forwarded_count += 1
                    post_link = f"https://t.me/{username}/{msg_id}" if username else f"Channel {channel_id} msg {msg_id}"
                    self.forwarded_posts.append({
                        'channel': username or title,
                        'message_id': msg_id,
                        'link': post_link
                    })
                    logger.info(f"   ✅ Переслано: {post_link}")
                    await asyncio.sleep(random.uniform(1.0, 2.0))
            
            # Реакция
            if existing_reactions and random.random() < REACTION_PROBABILITY:
                emoji = random.choice(existing_reactions)
                logger.info(f"   ❤️ Ставим реакцию {emoji} на #{msg_id}...")
                if await self.send_reaction(channel_id, msg_id, access_hash, emoji):
                    reacted_count += 1
                    post_link = f"https://t.me/{username}/{msg_id}" if username else f"Channel {channel_id} msg {msg_id}"
                    self.reacted_posts.append({
                        'channel': username or title,
                        'message_id': msg_id,
                        'emoji': emoji,
                        'link': post_link
                    })
                    logger.info(f"   ✅ Поставлена реакция: {post_link}")
                    await asyncio.sleep(random.uniform(1.0, 2.0))
            
            # Имитируем чтение
            await asyncio.sleep(reading_time)
        
        logger.info(f"")
        logger.info(f"📊 Статистика:")
        logger.info(f"   Прочитано: {len(messages_sorted)} сообщений")
        logger.info(f"   Переслано в избранное: {forwarded_count}")
        logger.info(f"   Поставлено реакций: {reacted_count}")
        
        return {
            'forwarded': forwarded_count,
            'reacted': reacted_count
        }
    
    async def run_test(self, max_channels: int = 5, test_mode: bool = True):
        """Запустить тест"""
        
        logger.info(f"")
        logger.info(f"=" * 80)
        logger.info(f"🚀 Тест взаимодействия с постами для сессии {self.session_id}")
        if test_mode:
            logger.info(f"🧪 Тестовый режим: обрабатываем последние сообщения в каналах")
        logger.info(f"=" * 80)
        
        # Получаем каналы с непрочитанными
        channels = await self.get_channels_with_unread(test_mode=test_mode)
        
        if not channels:
            logger.info(f"❌ Нет каналов с непрочитанными сообщениями")
            return
        
        # Обрабатываем несколько каналов
        channels_to_process = channels[:max_channels]
        
        for channel in channels_to_process:
            try:
                await self.read_channel_with_interactions(channel, max_messages=20)
            except Exception as e:
                logger.error(f"❌ Ошибка обработки канала: {e}", exc_info=True)
        
        # Итоговая статистика
        logger.info(f"")
        logger.info(f"=" * 80)
        logger.info(f"📊 ИТОГОВАЯ СТАТИСТИКА")
        logger.info(f"=" * 80)
        logger.info(f"")
        
        if self.forwarded_posts:
            logger.info(f"💾 Пересланные посты ({len(self.forwarded_posts)}):")
            for post in self.forwarded_posts:
                logger.info(f"   - {post['link']}")
        else:
            logger.info(f"💾 Посты не пересылались")
        
        logger.info(f"")
        
        if self.reacted_posts:
            logger.info(f"❤️ Посты с реакциями ({len(self.reacted_posts)}):")
            for post in self.reacted_posts:
                logger.info(f"   - {post['link']} (реакция: {post['emoji']})")
        else:
            logger.info(f"❤️ Реакции не ставились")
        
        logger.info(f"")
        logger.info(f"✅ Тест завершен")
        
        await self.telegram_client.close()


async def main():
    """Главная функция"""
    
    session_id = '27067'
    tester = PostInteractionTester(session_id)
    
    try:
        # Запускаем в тестовом режиме (обрабатываем последние сообщения даже если они прочитаны)
        await tester.run_test(max_channels=5, test_mode=True)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())

