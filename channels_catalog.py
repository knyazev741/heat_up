"""
Каталог РЕАЛЬНЫХ популярных Telegram-каналов
"""

# Каталог каналов - ТОЛЬКО РЕАЛЬНО СУЩЕСТВУЮЩИЕ!
CHANNELS_CATALOG = {
    # Официальные и верифицированные
    "official": [
        {"username": "@telegram", "title": "Telegram", "description": "Official Telegram channel", "category": "Официальные"},
        {"username": "@durov", "title": "Pavel Durov", "description": "Founder of Telegram", "category": "Официальные"},
    ],
    
    # Новости
    "news": [
        {"username": "@rt_russian", "title": "RT на русском", "description": "Новостной канал RT", "category": "Новости"},
        {"username": "@tass_agency", "title": "ТАСС", "description": "Информационное агентство ТАСС", "category": "Новости"},
        {"username": "@rian_ru", "title": "РИА Новости", "description": "Новости РИА", "category": "Новости"},
        {"username": "@rbc_news", "title": "РБК", "description": "Новости бизнеса", "category": "Новости"},
        {"username": "@bbcrussian", "title": "BBC Russian", "description": "BBC на русском", "category": "Новости"},
        {"username": "@meduzalive", "title": "Meduza", "description": "Независимые новости", "category": "Новости"},
    ],
    
    # Технологии и IT
    "tech": [
        {"username": "@techcrunch", "title": "TechCrunch", "description": "Tech news", "category": "Технологии"},
        {"username": "@tproger_official", "title": "Типичный программист", "description": "Для программистов", "category": "Технологии"},
        {"username": "@vcnews", "title": "VC.ru", "description": "Про стартапы и бизнес", "category": "Технологии"},
    ],
    
    # Криптовалюты
    "crypto": [
        {"username": "@forklog", "title": "ForkLog", "description": "Новости криптовалют", "category": "Крипто"},
        {"username": "@cryptonews", "title": "Crypto News", "description": "Crypto updates", "category": "Крипто"},
    ],
    
    # Развлечения и юмор
    "fun": [
        {"username": "@bash_im", "title": "Bash.im", "description": "Цитаты и юмор", "category": "Юмор"},
        {"username": "@anekdotov", "title": "Анекдоты", "description": "Свежие анекдоты", "category": "Юмор"},
        {"username": "@memepedia", "title": "Memepedia", "description": "Мемы", "category": "Юмор"},
    ],
    
    # Образование
    "education": [
        {"username": "@theoryandpractice", "title": "Теории и практики", "description": "Образовательный проект", "category": "Образование"},
        {"username": "@postnauka", "title": "ПостНаука", "description": "Научпоп", "category": "Образование"},
    ],
    
    # Кино и сериалы
    "cinema": [
        {"username": "@kinopoisk", "title": "Кинопоиск", "description": "Про кино", "category": "Кино"},
        {"username": "@cinemate", "title": "Синемат", "description": "Рецензии на фильмы", "category": "Кино"},
    ],
    
    # Музыка
    "music": [
        {"username": "@zvooq", "title": "Zvooq", "description": "Музыкальный сервис", "category": "Музыка"},
    ],
    
    # Спорт
    "sport": [
        {"username": "@sports", "title": "Спорт", "description": "Спортивные новости", "category": "Спорт"},
        {"username": "@championat", "title": "Чемпионат", "description": "Спорт", "category": "Спорт"},
    ],
    
    # Путешествия
    "travel": [
        {"username": "@aviasales", "title": "Aviasales", "description": "Дешевые билеты", "category": "Путешествия"},
    ],
    
    # Бизнес
    "business": [
        {"username": "@forbes_ru", "title": "Forbes Russia", "description": "Бизнес-журнал", "category": "Бизнес"},
        {"username": "@rusbase", "title": "Rusbase", "description": "Стартапы", "category": "Бизнес"},
    ],
}


def get_all_channels():
    """Получить все каналы из каталога"""
    all_channels = []
    for category, channels in CHANNELS_CATALOG.items():
        for ch in channels:
            ch_copy = ch.copy()
            ch_copy["catalog_category"] = category
            all_channels.append(ch_copy)
    return all_channels


def get_channels_by_categories(categories: list):
    """Получить каналы по определенным категориям"""
    channels = []
    for cat in categories:
        if cat in CHANNELS_CATALOG:
            for ch in CHANNELS_CATALOG[cat]:
                ch_copy = ch.copy()
                ch_copy["catalog_category"] = cat
                channels.append(ch_copy)
    return channels


def get_channels_by_keywords(keywords: list):
    """Найти каналы по ключевым словам в описании"""
    all_channels = get_all_channels()
    matching = []
    
    for ch in all_channels:
        text = f"{ch.get('title', '')} {ch.get('description', '')} {ch.get('category', '')}".lower()
        for keyword in keywords:
            if keyword.lower() in text:
                matching.append(ch)
                break
    
    return matching
