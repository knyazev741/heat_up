from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    openai_api_key: str
    telegram_api_base_url: str = "http://localhost:8000"
    telegram_api_key: str = ""
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"


settings = Settings()


# Pool of channels and chats for LLM to choose from
# These are diverse, popular, and safe channels
CHANNEL_POOL = [
    # News & Media
    {"username": "@durov", "description": "Pavel Durov's official channel"},
    {"username": "@telegram", "description": "Telegram official news and updates"},
    {"username": "@bbcnews", "description": "BBC News"},
    {"username": "@cnn", "description": "CNN Breaking News"},
    
    # Technology
    {"username": "@tech", "description": "Technology news and trends"},
    {"username": "@programming", "description": "Programming discussions"},
    {"username": "@python", "description": "Python programming community"},
    {"username": "@javascript", "description": "JavaScript developers"},
    
    # Entertainment
    {"username": "@movies", "description": "Movie discussions and recommendations"},
    {"username": "@music", "description": "Music lovers community"},
    {"username": "@gaming", "description": "Gaming news and discussions"},
    
    # Lifestyle
    {"username": "@travel", "description": "Travel tips and destinations"},
    {"username": "@food", "description": "Food recipes and cooking"},
    {"username": "@fitness", "description": "Fitness and health tips"},
    
    # Science & Education
    {"username": "@science", "description": "Science news and discoveries"},
    {"username": "@history", "description": "Historical facts and discussions"},
    {"username": "@books", "description": "Book recommendations and reviews"},
    
    # Business & Finance
    {"username": "@crypto", "description": "Cryptocurrency news"},
    {"username": "@business", "description": "Business and entrepreneurship"},
    {"username": "@finance", "description": "Finance and investing"},
]


# Actions timing (in seconds)
ACTION_DELAYS = {
    "min_between_actions": 3,
    "max_between_actions": 10,
    "min_read_time": 5,
    "max_read_time": 15,
}

