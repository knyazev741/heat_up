"""
PersonaAgent - генерация уникальных личностей для Telegram-аккаунтов
"""

import json
import logging
import random
import re
from typing import Dict, Any, Optional
from openai import OpenAI
from config import settings

logger = logging.getLogger(__name__)


class PersonaAgent:
    """
    Агент генерации уникальных личностей для Telegram-аккаунтов
    
    Создает реалистичные, разнообразные профили пользователей
    с учетом региональных особенностей и типов пользователей
    """
    
    def __init__(self):
        # Using DeepSeek API (OpenAI-compatible)
        self.client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com"
        )
        self.model = "deepseek-chat"  # DeepSeek model for better cost efficiency
    
    def extract_country_from_phone(self, phone_number: str) -> Optional[str]:
        """
        Определить страну по коду в номере телефона
        
        Args:
            phone_number: Номер телефона
            
        Returns:
            Название страны или None
        """
        # Убираем все нечисловые символы
        digits = re.sub(r'\D', '', phone_number)
        
        # Простое определение по коду страны (первые 1-3 цифры)
        country_codes = {
            '1': 'USA',
            '7': 'Russia',
            '34': 'Spain',
            '33': 'France',
            '39': 'Italy',
            '44': 'United Kingdom',
            '49': 'Germany',
            '52': 'Mexico',
            '55': 'Brazil',
            '86': 'China',
            '81': 'Japan',
            '82': 'South Korea',
            '91': 'India',
            '90': 'Turkey',
            '48': 'Poland',
            '380': 'Ukraine',
            '375': 'Belarus',
            '374': 'Armenia',
            '994': 'Azerbaijan',
            '995': 'Georgia',
            '998': 'Uzbekistan',
            '996': 'Kyrgyzstan',
            '992': 'Tajikistan',
            '993': 'Turkmenistan',
            '371': 'Latvia',
            '372': 'Estonia',
            '373': 'Moldova',
        }
        
        # Проверяем коды разной длины (от 3 до 1 цифры)
        for length in [3, 2, 1]:
            code = digits[:length]
            if code in country_codes:
                return country_codes[code]
        
        return None
    
    async def generate_persona(
        self, 
        phone_number: str, 
        country: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Генерирует уникальную личность на основе номера телефона
        
        Args:
            phone_number: Номер телефона
            country: Страна (если не указана, определяется по номеру)
            
        Returns:
            Dict с полями:
            - generated_name: имя и фамилия
            - age: возраст
            - gender: пол
            - occupation: профессия
            - city: город
            - country: страна
            - personality_traits: список черт характера
            - interests: список интересов
            - communication_style: стиль общения
            - activity_level: уровень активности
            - full_description: полное описание
            - background_story: история персонажа
        """
        
        # Определяем страну если не указана
        if not country:
            country = self.extract_country_from_phone(phone_number)
            if not country:
                country = "Russia"  # Default
        
        logger.info(f"Generating persona for phone {phone_number[-4:]}**** from {country}")
        
        prompt, hints = self._build_persona_prompt(phone_number, country)
        logger.info(f"🎲 Diversity hints: {hints}")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=1.0,  # Максимальная температура для максимального разнообразия
                max_tokens=2048,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты - эксперт по созданию реалистичных цифровых личностей. Всегда отвечай в формате JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            response_text = response.choices[0].message.content
            
            logger.info("=" * 100)
            logger.info("🎭 PERSONA GENERATION")
            logger.info("=" * 100)
            logger.info(f"Country: {country}")
            logger.info(f"Response:\n{response_text}")
            logger.info("=" * 100)
            
            # Parse JSON
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text.strip()
            
            persona_data = json.loads(json_str)
            
            # Валидация и нормализация
            persona = self._validate_persona(persona_data, country)
            
            logger.info(f"✅ Successfully generated persona: {persona.get('generated_name')}, "
                       f"{persona.get('age')} y.o., {persona.get('occupation')}")
            
            return persona
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            logger.error(f"Response text: {response_text[:500]}")
            return self._get_fallback_persona(country)
        except Exception as e:
            logger.error(f"Error generating persona: {e}")
            return self._get_fallback_persona(country)
    
    def _build_persona_prompt(self, phone_number: str, country: str) -> tuple:
        """
        Построить промпт для генерации личности
        
        Returns:
            tuple: (prompt, hints_dict) - промпт и подсказки для логирования
        """
        
        # Категории профессий для принудительного разнообразия
        occupation_categories = [
            # Образование
            ["учитель", "преподаватель", "воспитатель", "тренер"],
            # Медицина
            ["врач", "медсестра", "фармацевт", "стоматолог"],
            # Торговля
            ["продавец", "кассир", "менеджер по продажам", "администратор магазина"],
            # Производство
            ["рабочий", "токарь", "электрик", "сварщик", "механик"],
            # Транспорт
            ["водитель", "таксист", "курьер", "логист"],
            # Офис
            ["бухгалтер", "секретарь", "офис-менеджер", "HR-специалист"],
            # IT (но не все!)
            ["программист", "системный администратор", "тестировщик"],
            # Строительство
            ["строитель", "прораб", "отделочник", "архитектор"],
            # Сфера услуг
            ["парикмахер", "повар", "официант", "уборщик", "консультант"],
            # Креатив
            ["дизайнер", "фотограф", "художник", "музыкант"],
            # Студенты и прочие
            ["студент", "фрилансер", "пенсионер", "домохозяйка", "предприниматель"],
        ]
        
        # Выбираем случайную категорию
        chosen_category = random.choice(occupation_categories)
        category_hint = ", ".join(chosen_category)
        
        # Генерируем случайные характеристики для подсказки
        age_hint = random.choice([
            "молодой (18-25)", "средний возраст (26-40)", 
            "зрелый (41-55)", "старший возраст (56-65)"
        ])
        
        interest_hint = random.choice([
            "спорт и фитнес", "кулинария", "садоводство", "чтение", 
            "путешествия", "игры", "музыка", "кино и сериалы",
            "автомобили", "рукоделие", "фотография", "домашние животные"
        ])
        
        prompt = f"""Создай уникальную, правдоподобную личность для пользователя Telegram из страны {country}.

🎲 СЛУЧАЙНЫЕ ПАРАМЕТРЫ ДЛЯ ЭТОЙ ГЕНЕРАЦИИ:
- Профессия из категории: {category_hint}
- Возрастная группа: {age_hint}
- Один из основных интересов: {interest_hint}

⚠️ КРИТИЧЕСКИ ВАЖНО - РАЗНООБРАЗИЕ:
- НЕ повторяй одни и те же профессии подряд
- НЕ делай всех одного возраста (варьируй от 18 до 65)
- НЕ используй шаблонные интересы
- НЕ делай всех активными/пассивными - варьируй
- ИЗБЕГАЙ клише типа "IT-специалист в свободное время увлекается крипто"

Личность должна включать:

1. Базовая информация:
   - generated_name: Имя и фамилия (соответствуют культуре страны {country})
   - age: Возраст (18-65, реалистичный для профессии)
   - gender: "male" или "female"
   - city: Город проживания (реальный город из {country})
   - country: "{country}"
   
2. Работа и образование:
   - occupation: Род занятий (будь ОЧЕНЬ реалистичен, обычные профессии!)
   
3. Характер и интересы:
   - personality_traits: Массив из 3-5 черт характера (например: ["любознательный", "осторожный", "дружелюбный"])
   - interests: Массив из 3-7 интересов/хобби (например: ["футбол", "кино", "готовка"])
   - communication_style: "casual" (неформальный), "formal" (формальный), или "emoji_heavy" (много эмодзи)
   - activity_level: "passive" (пассивный наблюдатель), "moderate" (средний), или "active" (очень активный)
   - min_daily_activity: Минимум сколько раз в день заходит в мессенджеры (2-6)
   - max_daily_activity: Максимум сколько раз в день заходит в мессенджеры (4-10)
     * Пассивные люди, пенсионеры, занятые профессионалы → min:2, max:4
     * Обычные пользователи, работающие люди → min:3, max:6
     * Активные юзеры, студенты, молодежь, блогеры → min:5, max:9
     * Учитывай профессию, возраст и характер! Диапазон делает поведение естественным.

4. История и описание:
   - background_story: 2-3 предложения о том, почему человек использует Telegram, что ищет в мессенджере
   - full_description: Развернутое описание личности (3-4 абзаца), которое будет использоваться в промптах для генерации действий. 
     Опиши:
     * Кто этот человек, чем занимается в жизни
     * Что его интересует, какие у него хобби
     * Как он обычно ведет себя в соцсетях и мессенджерах
     * Какой у него стиль общения

💡 ПРИМЕРЫ ХОРОШЕГО РАЗНООБРАЗИЯ:
- Водитель такси, 52 года, интересы: рыбалка, новости, футбол
- Студентка, 21 год, интересы: k-pop, аниме, фотография
- Медсестра, 38 лет, интересы: йога, садоводство, чтение
- Пенсионер, 63 года, интересы: шахматы, история, внуки
- Фрилансер-дизайнер, 29 лет, интересы: путешествия, кофе, архитектура

Формат ответа - ТОЛЬКО JSON (без дополнительного текста):

{{
  "generated_name": "...",
  "age": ...,
  "gender": "...",
  "occupation": "...",
  "city": "...",
  "country": "{country}",
  "personality_traits": ["...", "..."],
  "interests": ["...", "..."],
  "communication_style": "...",
  "activity_level": "...",
  "min_daily_activity": 3,
  "max_daily_activity": 6,
  "background_story": "...",
  "full_description": "..."
}}

🎯 ФИНАЛЬНАЯ ИНСТРУКЦИЯ:
Используй подсказки выше (категория профессии, возраст, интересы), но добавь свою креативность!
Каждая генерация должна быть УНИКАЛЬНОЙ - не копируй предыдущие профили!
ОБЯЗАТЕЛЬНО варьируй: профессию, возраст, пол, характер, интересы, активность!"""
        
        hints = {
            "occupation_category": category_hint,
            "age_group": age_hint,
            "interest": interest_hint
        }
        
        return prompt, hints
    
    def _validate_persona(self, persona_data: Dict[str, Any], country: str) -> Dict[str, Any]:
        """Валидация и нормализация данных персоны"""
        
        # Базовые поля с fallback
        persona = {
            "generated_name": persona_data.get("generated_name", "Unknown User"),
            "age": min(65, max(18, persona_data.get("age", 30))),
            "gender": persona_data.get("gender", "male"),
            "occupation": persona_data.get("occupation", "employee"),
            "city": persona_data.get("city", "Unknown City"),
            "country": persona_data.get("country", country),
            "personality_traits": persona_data.get("personality_traits", ["friendly"]),
            "interests": persona_data.get("interests", ["technology"]),
            "communication_style": persona_data.get("communication_style", "casual"),
            "activity_level": persona_data.get("activity_level", "moderate"),
            "min_daily_activity": min(10, max(2, persona_data.get("min_daily_activity", 3))),
            "max_daily_activity": min(10, max(2, persona_data.get("max_daily_activity", 6))),
            "background_story": persona_data.get("background_story", "A regular Telegram user."),
            "full_description": persona_data.get("full_description", "A regular person using Telegram for communication.")
        }
        
        # Валидация communication_style
        if persona["communication_style"] not in ["casual", "formal", "emoji_heavy"]:
            persona["communication_style"] = "casual"
        
        # Валидация activity_level
        if persona["activity_level"] not in ["passive", "moderate", "active"]:
            persona["activity_level"] = "moderate"
        
        # Валидация диапазона активности (min < max)
        if persona["min_daily_activity"] >= persona["max_daily_activity"]:
            persona["max_daily_activity"] = persona["min_daily_activity"] + 2
        
        return persona
    
    def _get_fallback_persona(self, country: str) -> Dict[str, Any]:
        """Резервная персона если LLM failed"""
        
        occupations = [
            "teacher", "doctor", "engineer", "salesperson", "driver",
            "accountant", "student", "manager", "worker", "employee"
        ]
        
        names_by_country = {
            "Russia": ["Иван Иванов", "Мария Петрова", "Алексей Смирнов", "Анна Кузнецова"],
            "USA": ["John Smith", "Mary Johnson", "Michael Brown", "Jennifer Davis"],
            "Germany": ["Hans Mueller", "Anna Schmidt", "Michael Wagner", "Sarah Fischer"],
            "default": ["Alex Johnson", "Maria Smith", "Ivan Petrov", "Anna Williams"]
        }
        
        names = names_by_country.get(country, names_by_country["default"])
        
        return {
            "generated_name": random.choice(names),
            "age": random.randint(25, 45),
            "gender": random.choice(["male", "female"]),
            "occupation": random.choice(occupations),
            "city": "Unknown City",
            "country": country,
            "personality_traits": ["friendly", "curious"],
            "interests": ["technology", "news"],
            "communication_style": "casual",
            "activity_level": "moderate",
            "min_daily_activity": 3,
            "max_daily_activity": 6,
            "background_story": "A regular Telegram user looking to stay connected with friends and follow interesting content.",
            "full_description": "A regular person who uses Telegram for daily communication and staying informed about topics of interest."
        }

