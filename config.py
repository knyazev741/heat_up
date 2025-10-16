from pydantic_settings import BaseSettings
from typing import List
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    openai_api_key: str
    telegram_api_base_url: str = "http://localhost:8000"
    telegram_api_key: str = ""
    log_level: str = "INFO"
    tgstat_api_token: str = "2539dfbdf80afd5c45d0c8f86cc9d21a"
    session_history_days: int = 30
    database_path: str = "sessions.db"
    
    # Scheduler settings
    scheduler_check_interval: int = 1800  # 30 минут
    scheduler_enabled: bool = True
    
    # Warmup stages
    warmup_max_stage: int = 14  # 14 дней базового прогрева
    
    # Daily activity
    default_daily_activity_count: int = 3
    min_daily_activity_count: int = 2
    max_daily_activity_count: int = 5
    
    # Search settings
    search_chats_per_persona: int = 20
    use_web_search: bool = False
    
    # Content randomization
    enable_content_randomization: bool = True
    message_variations_count: int = 10
    
    class Config:
        env_file = ".env"


settings = Settings()


# Hardcoded verified channels as fallback
# УБРАЛИ @telegram и @durov - слишком очевидно и все на них подписываются
VERIFIED_CHANNELS = [
    # Пустой список - будем использовать только из channels_catalog
]


def load_channels_from_file(filepath: str = "channels_data.json") -> List[dict]:
    """
    Load channels from JSON file
    
    Args:
        filepath: Path to channels JSON file
        
    Returns:
        List of channel dictionaries
    """
    file_path = Path(filepath)
    
    if not file_path.exists():
        logger.warning(f"Channels file not found: {filepath}. Using verified channels only.")
        return []
    
    try:
        with file_path.open('r', encoding='utf-8') as f:
            channels = json.load(f)
            logger.info(f"Loaded {len(channels)} channels from {filepath}")
            return channels
    except Exception as e:
        logger.error(f"Error loading channels from file: {e}")
        return []


def load_bots_from_file(filepath: str = "bots_data.json") -> List[dict]:
    """
    Load bots from JSON file
    
    Args:
        filepath: Path to bots JSON file
        
    Returns:
        List of bot dictionaries
    """
    file_path = Path(filepath)
    
    if not file_path.exists():
        logger.warning(f"Bots file not found: {filepath}. No bots available.")
        return []
    
    try:
        with file_path.open('r', encoding='utf-8') as f:
            bots = json.load(f)
            logger.info(f"Loaded {len(bots)} bots from {filepath}")
            return bots
    except Exception as e:
        logger.error(f"Error loading bots from file: {e}")
        return []


def build_channel_pool() -> List[dict]:
    """
    Build the channel pool by merging verified channels with fetched channels
    
    Returns:
        Combined list of channels
    """
    # Start with verified channels
    pool = VERIFIED_CHANNELS.copy()
    
    # Load channels from file
    fetched_channels = load_channels_from_file()
    
    # Merge, avoiding duplicates
    seen_usernames = {ch["username"].lower() for ch in pool}
    
    for channel in fetched_channels:
        username = channel["username"].lower()
        if username not in seen_usernames:
            pool.append(channel)
            seen_usernames.add(username)
    
    logger.info(f"Built channel pool with {len(pool)} total channels")
    return pool


# Pool of channels and chats for LLM to choose from
# Merges verified channels with TGStat-fetched channels
CHANNEL_POOL = build_channel_pool()

# Pool of bots for LLM to interact with
BOTS_POOL = load_bots_from_file()


# Actions timing (in seconds)
ACTION_DELAYS = {
    "min_between_actions": 3,
    "max_between_actions": 10,
    "min_read_time": 5,
    "max_read_time": 15,
}


# Рекомендации по прогреву (зеленые/красные флаги) для каждой стадии
WARMUP_GUIDELINES = {
    1: {
        "description": "Новый пользователь, первый вход",
        "max_actions": 3,
        "allowed_actions": ["update_profile", "idle"],
        "max_joins": 0,
        "max_messages": 0,
        "recommendations": [
            "Только настройка профиля",
            "Добавить фото с лицом",
            "Установить реалистичное имя и фамилию",
            "Больше ничего не делать!"
        ]
    },
    2: {
        "description": "Второй день - заполнение профиля",
        "max_actions": 5,
        "allowed_actions": ["update_profile", "join_channel", "read_messages", "idle", "view_profile"],
        "max_joins": 1,
        "max_messages": 0,
        "recommendations": [
            "Заполнить био (О себе)",
            "Можно вступить в 1 верифицированный канал",
            "Больше idle - показать естественное поведение",
            "Не писать сообщения"
        ]
    },
    3: {
        "description": "Третий день - первые шаги",
        "max_actions": 7,
        "allowed_actions": ["join_channel", "read_messages", "idle", "view_profile", "update_privacy"],
        "max_joins": 2,
        "max_messages": 0,
        "recommendations": [
            "Вступить в 1-2 интересных канала",
            "Читать сообщения в каналах",
            "Настроить приватность аккаунта",
            "Пока без сообщений и реакций"
        ]
    },
    4: {
        "description": "Четвертый день - исследование",
        "max_actions": 7,
        "allowed_actions": ["join_channel", "read_messages", "idle", "view_profile", "sync_contacts"],
        "max_joins": 2,
        "max_messages": 0,
        "recommendations": [
            "Можно добавить контакты",
            "Продолжить изучать каналы",
            "Разнообразить действия"
        ]
    },
    5: {
        "description": "Пятый день - первая активность",
        "max_actions": 10,
        "allowed_actions": ["join_channel", "read_messages", "idle", "react_to_message", "message_bot", "view_profile"],
        "max_joins": 2,
        "max_messages": 0,
        "recommendations": [
            "Начать ставить реакции на посты",
            "Можно написать боту (/start)",
            "Вступить в чаты по интересам",
            "Не писать в группы, только боту"
        ]
    },
    6: {
        "description": "Шестой день - больше вовлеченности",
        "max_actions": 10,
        "allowed_actions": ["join_channel", "read_messages", "idle", "react_to_message", "message_bot", "view_profile"],
        "max_joins": 2,
        "max_messages": 0,
        "recommendations": [
            "Активнее ставить реакции",
            "Исследовать ботов",
            "Показывать вовлеченность"
        ]
    },
    7: {
        "description": "Седьмой день - закрепление",
        "max_actions": 12,
        "allowed_actions": ["join_channel", "read_messages", "idle", "react_to_message", "message_bot", "view_profile"],
        "max_joins": 3,
        "max_messages": 0,
        "recommendations": [
            "Можно вступить в локальные чаты города",
            "Больше реакций",
            "Разнообразие действий"
        ]
    },
    8: {
        "description": "Восьмой день - первые сообщения",
        "max_actions": 12,
        "allowed_actions": ["join_channel", "read_messages", "idle", "react_to_message", "message_bot", "view_profile", "reply_in_chat"],
        "max_joins": 2,
        "max_messages": 1,
        "recommendations": [
            "Можно написать ОДИН короткий ответ в группе",
            "Ответить на чей-то вопрос",
            "Быть осторожным с текстом"
        ]
    },
    9: {
        "description": "Девятый день - больше общения",
        "max_actions": 15,
        "allowed_actions": ["join_channel", "read_messages", "idle", "react_to_message", "message_bot", "reply_in_chat", "view_profile"],
        "max_joins": 2,
        "max_messages": 2,
        "recommendations": [
            "До 2 сообщений в разные группы",
            "Участвовать в обсуждениях",
            "Уникальные сообщения"
        ]
    },
    10: {
        "description": "Десятый день - создание групп",
        "max_actions": 15,
        "allowed_actions": ["join_channel", "read_messages", "idle", "react_to_message", "reply_in_chat", "create_group", "view_profile"],
        "max_joins": 2,
        "max_messages": 2,
        "recommendations": [
            "Можно создать небольшую группу",
            "Добавить 1-2 контакта",
            "Продолжать общение в чатах"
        ]
    },
    11: {
        "description": "Одиннадцатый день - усиление активности",
        "max_actions": 15,
        "allowed_actions": ["join_channel", "read_messages", "idle", "react_to_message", "reply_in_chat", "view_profile"],
        "max_joins": 2,
        "max_messages": 3,
        "recommendations": [
            "До 3 сообщений в день",
            "Разные чаты",
            "Естественное поведение"
        ]
    },
    12: {
        "description": "Двенадцатый день - форварды",
        "max_actions": 15,
        "allowed_actions": ["join_channel", "read_messages", "idle", "react_to_message", "reply_in_chat", "forward_message", "view_profile"],
        "max_joins": 2,
        "max_messages": 3,
        "recommendations": [
            "Можно форвардить интересные посты",
            "В свою группу или контактам",
            "Продолжать общение"
        ]
    },
    13: {
        "description": "Тринадцатый день - стабильная активность",
        "max_actions": 15,
        "allowed_actions": ["join_channel", "read_messages", "idle", "react_to_message", "reply_in_chat", "forward_message", "view_profile"],
        "max_joins": 3,
        "max_messages": 3,
        "recommendations": [
            "Поддерживать стабильную активность",
            "Разнообразие действий",
            "Естественное поведение"
        ]
    },
    14: {
        "description": "Четырнадцатый день - готовность к работе",
        "max_actions": 15,
        "allowed_actions": ["join_channel", "read_messages", "idle", "react_to_message", "reply_in_chat", "forward_message", "view_profile"],
        "max_joins": 3,
        "max_messages": 5,
        "recommendations": [
            "Аккаунт готов к рабочим задачам",
            "Можно постепенно начинать рассылки",
            "Соблюдать лимиты флудвейта"
        ]
    }
}


# Лимиты для избежания флудвейта
FLOOD_PREVENTION = {
    "max_messages_per_hour": 2,
    "max_joins_per_day": 3,
    "max_joins_per_session": 3,
    "min_delay_between_messages": 180,  # 3 минуты
    "min_delay_between_joins": 600,  # 10 минут
    "max_same_message_reuse": 3,  # Сколько раз можно использовать одно сообщение
}


# Красные флаги (что НЕ делать)
RED_FLAGS = [
    "Отправка одинаковых сообщений в разные чаты",
    "Слишком много действий сразу после долгой паузы",
    "Вступление в более 3 чатов за одну сессию",
    "Отправка сообщений чаще 1 раза в 3 часа",
    "Массовая рассылка в первые дни",
    "Использование шаблонных текстов",
    "Слишком быстрые действия (без пауз)",
    "Вступление только в рекламные группы"
]


# Зеленые флаги (что НУЖНО делать)
GREEN_FLAGS = [
    "Постепенное увеличение активности день за днём",
    "Разнообразие действий (не только join → read)",
    "Участие в диалогах (ответы на вопросы других)",
    "Реакции на сообщения (показываешь вовлеченность)",
    "Паузы между действиями разной длины",
    "Уникальные сообщения для каждого чата",
    "Чтение сообщений перед отправкой своих",
    "Естественное поведение как у обычного человека",
    "Вступление в разные типы чатов (новости, хобби, город)",
    "Настройка профиля в первые дни"
]

