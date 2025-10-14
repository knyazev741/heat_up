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
    
    class Config:
        env_file = ".env"


settings = Settings()


# Hardcoded verified channels as fallback
VERIFIED_CHANNELS = [
    {"username": "@durov", "description": "Pavel Durov's official channel", "category": "Verified"},
    {"username": "@telegram", "description": "Telegram official news and updates", "category": "Verified"},
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

