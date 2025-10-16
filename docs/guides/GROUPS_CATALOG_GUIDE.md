# 💬 Каталог групп и чатов для общения

## ✅ ЧТО ДОБАВЛЕНО:

### **1. Файл `groups_catalog.py`**

Каталог **ГРУПП** (не каналов!) где можно:
- 💬 Общаться
- ❓ Задавать вопросы  
- 🗣️ Участвовать в диалогах

### **2. Категории групп:**

#### **Города России (10+ городов):**
```
- Москва: moscowchat, moscowhelp
- СПб: spbchat, piterchat
- Екатеринбург: ekbchat
- Новосибирск: nskchat
- Казань: kazanchat
- Самара: samarachat
- Нижний Новгород: nnchat
- Краснодар: krasnodarchat
- Ростов: rostovchat
- Саратов: saratovchat
```

#### **Хобби и интересы:**
```
- IT: python_ru, webdevrus, ru_javascript
- Фотография: photographers_ru, photo_help
- Рыбалка: fishing_ru, fishermen_chat
- Кулинария: cookers_ru, cooking_chat
- Садоводство: gardeners_ru, dacha_chat
- Путешествия: travelers_ru, travel_help
- Игры: gamers_ru, dota2_ru, csgo_ru
- Музыка: musicians_ru, guitar_ru
- Спорт: football_ru, fitness_ru, running_ru
- Авто: auto_ru, autohelp_ru
```

#### **Профессии:**
```
- Учителя: teachers_ru
- Врачи/Медсестры: doctors_ru, nurses_ru
```

#### **Барахолки:**
```
- flea_market_ru, tech_market_ru
```

---

## 🔄 КАК ЭТО РАБОТАЕТ:

### **1. SearchAgent теперь ищет И каналы И группы:**

```python
# Приоритет:
city_groups = get_groups_by_city(persona.city)          # 1. Группы города
interest_groups = get_groups_by_interests(persona.interests)  # 2. Группы интересов
channels = get_channels_by_keywords(keywords)           # 3. Каналы
```

### **2. LLM ранжирует с приоритетом на группы:**

```
💬 ГРУППЫ > 📢 КАНАЛЫ
Группы города: score 0.9+
Группы интересов: score 0.7+
Каналы: score 0.3-0.6
```

### **3. В базе сохраняется `chat_type`:**

```sql
chat_type: 'group' | 'supergroup' | 'channel'
```

---

## 📊 ПРИМЕР:

**Персона:** Рыбак из Саратова, 52 года

**Найдет:**
1. 💬 `saratovchat` (группа, score: 0.95) - ГОРОД
2. 💬 `fishing_ru` (группа, score: 0.85) - ИНТЕРЕС
3. 💬 `fishermen_chat` (группа, score: 0.80) - ИНТЕРЕС
4. 📢 `@sports` (канал, score: 0.4) - средний приоритет

**Вступит в ГРУППЫ** где можно общаться!

---

## 🧪 КАК ПРОВЕРИТЬ:

```bash
# Добавь новый аккаунт
curl -X POST http://localhost:8000/accounts/add \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test_groups_001"}'

# Посмотри что нашлось
sqlite3 sessions.db \
"SELECT chat_username, chat_type, relevance_score 
 FROM discovered_chats 
 WHERE account_id=(SELECT id FROM accounts WHERE session_id='test_groups_001')
 ORDER BY relevance_score DESC LIMIT 10"
```

Должны быть:
- `chat_type = 'group'` или `'supergroup'`
- Группы города с score > 0.8
- Группы интересов с score > 0.7

---

## ⚠️ ВАЖНО:

### **Эти username ПРИМЕРНЫЕ!**

В `groups_catalog.py` указаны **гипотетические** имена групп:
- `moscowchat`
- `python_ru`
- `fishing_ru`

Они могут **не существовать** в реальности!

### **Как добавить РЕАЛЬНЫЕ группы:**

1. Найди реальные публичные группы в Telegram
2. Проверь их username
3. Добавь в `groups_catalog.py`:

```python
"moscow": [
    {"username": "реальный_username", "title": "...", "description": "...", "chat_type": "supergroup"},
],
```

---

## 🎯 ПРЕИМУЩЕСТВА:

✅ Аккаунты вступают в ГРУППЫ для общения
✅ Приоритет на группы города (местное общение!)
✅ Группы по интересам (тематическое общение!)
✅ Более естественное поведение
✅ Можно участвовать в диалогах

---

## 📝 TODO (для улучшения):

1. **Заменить гипотетические username на реальные**
2. Добавить больше городов
3. Добавить больше профессиональных групп
4. Добавить группы университетов/вузов
5. Добавить тематические чаты (кино, сериалы, и т.д.)

---

**Теперь система находит ГРУППЫ для общения, а не только каналы для чтения!** 🎉

