# План развития системы прогрева Heat Up

## Цель

Сделать поведение ботов неотличимым от реальных пользователей Telegram. Каждый аккаунт — уникальная личность со своими привычками, интересами и паттернами общения.

**Ключевая идея:** Сначала тренируем ботов в контролируемой среде (между собой), потом выпускаем в реальные чаты.

---

## Текущее состояние

### Что уже реализовано

| Компонент | Статус | Описание |
|-----------|--------|----------|
| 14-дневная система стадий | ✅ | Градиентное увеличение активности |
| LLM-генерация планов | ✅ | DeepSeek генерирует уникальные последовательности |
| Персоны аккаунтов | ✅ | Имя, интересы, характер, история |
| Базовые действия | ✅ | join_channel, read_messages, react, idle |
| Антидетект (базовый) | ✅ | Случайные задержки, лимиты по стадиям |
| История действий | ✅ | SQLite хранит всё для контекста LLM |

### Текущие типы аккаунтов

| Тип | Количество | Возможности |
|-----|------------|-------------|
| Прогрев (активные) | ~120 | Полный функционал, могут писать первыми |
| Заспамленные | 50-200 | Не могут писать первыми в ЛС, могут отвечать и писать в группах |

### Ограничения текущей реализации

1. **Только каналы** — боты не участвуют в чатах как живые люди
2. **Нет личного общения** — боты не переписываются друг с другом
3. **Нет контекстного понимания** — реплики не связаны с обсуждением
4. **Изолированные аккаунты** — нет социальных связей между ними

---

## Roadmap развития

```
┌─────────────────────────────────────────────────────────────────────┐
│  ФАЗА 1: Контролируемая среда (между своими ботами)                 │
│  ├── 1.1 Вспомогательные аккаунты (спамблок)                        │
│  ├── 1.2 ЛС диалоги между ботами                                    │
│  ├── 1.3 Приватные группы ботов                                     │
│  └── 1.4 Conversation Engine                                        │
├─────────────────────────────────────────────────────────────────────┤
│  ФАЗА 2: Реальные групповые чаты                                    │
│  ├── 2.1 Поиск тематических чатов                                   │
│  ├── 2.2 Анализ контекста                                           │
│  ├── 2.3 Контекстные ответы                                         │
│  └── 2.4 Ответы живым людям                                         │
├─────────────────────────────────────────────────────────────────────┤
│  ФАЗА 3: Улучшение естественности                                   │
│  ├── 3.1 Паттерны времени                                           │
│  ├── 3.2 Stories, стикеры, голосовые                                │
│  └── 3.3 Эмоциональные реакции                                      │
├─────────────────────────────────────────────────────────────────────┤
│  ФАЗА 4: Тестирование и мониторинг (ongoing)                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Фаза 1: Контролируемая среда (ЗАВЕРШЕНО 2026-01-08)

### Статус: ЗАВЕРШЕНО

Полный отчет: `docs/archive/reports/PHASE_1_COMPLETION_REPORT.md`

#### Реализовано:
- [x] ConversationAgent (LLM генерация сообщений)
- [x] ConversationEngine (координатор диалогов)
- [x] Проверка status=1 через Admin API
- [x] Импорт контактов для получения access_hash
- [x] Отправка DM через raw TL методы
- [x] Интеграция в scheduler

#### Протестировано:
- [x] Полный поток диалога (3+ сообщения)
- [x] Блокировка status=1 сессий
- [x] Чередование отправителей
- [x] Естественные русские сообщения

### Почему сначала это?

1. **Безопасно** — общаемся только между своими аккаунтами
2. **Контролируемо** — можем отлаживать без риска банов
3. **Создаёт историю** — у аккаунтов появляются реальные диалоги
4. **Тренировка LLM** — отрабатываем генерацию до выхода в реальные чаты

---

### 1.1 Вспомогательные аккаунты (спамблок)

**Цель:** Использовать старые заспамленные аккаунты как собеседников

#### Типы аккаунтов в системе

```
┌─────────────────────────────────────────────────────────────┐
│                    ПУЛ АККАУНТОВ                            │
├─────────────────────────────────────────────────────────────┤
│  WARMUP (прогрев)           │  HELPER (вспомогательные)     │
│  ─────────────────          │  ────────────────────────     │
│  • Активный прогрев         │  • Вечный спамблок            │
│  • Могут писать первыми     │  • НЕ могут писать первыми    │
│  • 14-дневный цикл          │  • Могут ОТВЕЧАТЬ в ЛС        │
│  • Полный функционал        │  • Могут писать в группах     │
│  • ~120 аккаунтов           │  • 50-200 аккаунтов           │
└─────────────────────────────────────────────────────────────┘
```

---

### КРИТИЧЕСКИЕ ПРАВИЛА: Ограничения DM по статусу сессии

#### Правило 1: status=1 в Admin API — запрет инициации DM

Если у сессии в базе Admin API `status = 1`, то **ЗАПРЕЩЕНО** начинать новый диалог с этой сессией (писать первым в ЛС).

```
┌─────────────────────────────────────────────────────────────────────────┐
│  СЕССИЯ СО status=1 (ограниченная)                                       │
├─────────────────────────────────────────────────────────────────────────┤
│  ❌ НЕЛЬЗЯ:                        │  ✅ МОЖНО:                          │
│  ─────────────────────────────     │  ────────────────────────────────  │
│  • Писать первым в ЛС              │  • Писать самой (инициировать)      │
│    (начинать новый диалог)         │  • Отвечать на входящие сообщения   │
│                                    │  • Продолжать существующий диалог   │
│                                    │  • Писать в групповых чатах         │
│                                    │  • Участвовать в приватных группах  │
└─────────────────────────────────────────────────────────────────────────┘
```

**Алгоритм проверки перед началом DM:**

```python
async def can_initiate_dm_to_session(target_session_id: str) -> bool:
    """Проверка можно ли начать DM с сессией"""

    # 1. Проверить есть ли уже диалог с этой сессией
    existing_conversation = await db.get_conversation_between(
        my_session_id, target_session_id
    )
    if existing_conversation:
        return True  # Продолжаем существующий диалог

    # 2. Дёргаем Admin API для проверки статуса
    session_info = await admin_api.get_session(target_session_id)

    if session_info.get("status") == 1:
        logger.info(f"Skip DM to {target_session_id}: status=1")
        return False  # Нельзя начинать новый диалог

    return True  # Можно писать
```

#### Правило 2: Спамблок (вечный) — ограничения инициатора

Сессии с вечным спамблоком (`spamblock=true AND unban_date IS NULL`):

```
┌─────────────────────────────────────────────────────────────────────────┐
│  СЕССИЯ СО СПАМБЛОКОМ (вечным)                                           │
├─────────────────────────────────────────────────────────────────────────┤
│  ❌ НЕЛЬЗЯ:                        │  ✅ МОЖНО:                          │
│  ─────────────────────────────     │  ────────────────────────────────  │
│  • Писать первым в ЛС              │  • Отвечать если получили ответ     │
│    (инициировать новый диалог)     │  • Писать если добавлен в контакты  │
│                                    │  • Писать в групповых чатах         │
│                                    │  • Участвовать в приватных группах  │
└─────────────────────────────────────────────────────────────────────────┘
```

**Важно:** Спамблок-сессия может продолжать диалог если:
1. Ей ответили на её сообщение (диалог открыт)
2. Её добавили в контакты (разрешение на ЛС)

#### Правило 3: Минимальная стадия для DM-активности

DM-действия (личные диалоги) доступны **только со 2-й стадии прогрева и выше**.

```python
MIN_STAGE_FOR_DM = 2  # Стадии 0-1 — только каналы, стадия 2+ — можно DM

async def is_eligible_for_dm_actions(session_id: str) -> bool:
    """Проверка готовности сессии к DM-действиям"""

    account = await db.get_account_by_session_id(session_id)

    if account.warmup_stage < MIN_STAGE_FOR_DM:
        return False

    # Проверить не спамблок ли
    if account.account_type == 'helper' or not account.can_initiate_dm:
        return False  # Helper может только отвечать

    return True
```

#### Матрица разрешений DM

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  ИНИЦИАТОР (кто пишет)      →  ПОЛУЧАТЕЛЬ (кому пишут)                       │
├──────────────────────────────────────────────────────────────────────────────┤
│                               │ status≠1   │ status=1   │ spamblock │ helper │
│  ─────────────────────────────┼────────────┼────────────┼───────────┼────────│
│  warmup (стадия 2+)           │     ✅     │     ❌     │     ✅    │   ✅   │
│  warmup (стадия 0-1)          │     ❌     │     ❌     │     ❌    │   ❌   │
│  helper (спамблок)            │     ❌*    │     ❌     │     ❌    │   ❌   │
│                               │            │            │           │        │
│  * может отвечать если открыт диалог или добавлен в контакты                 │
└──────────────────────────────────────────────────────────────────────────────┘
```

#### Логика ConversationEngine с учётом правил

```python
async def select_target_for_new_dm(initiator_session_id: str) -> Optional[str]:
    """Выбор цели для нового DM с учётом всех ограничений"""

    initiator = await db.get_account_by_session_id(initiator_session_id)

    # 1. Проверить может ли инициатор начинать DM
    if initiator.warmup_stage < MIN_STAGE_FOR_DM:
        return None

    if not initiator.can_initiate_dm:
        return None

    # 2. Получить пул потенциальных собеседников
    potential_targets = await db.get_accounts_for_dm(
        exclude_session_id=initiator_session_id,
        account_types=['warmup', 'helper']  # Можно писать и warmup и helpers
    )

    # 3. Фильтрация по статусу через Admin API
    valid_targets = []
    for target in potential_targets:
        # Проверить нет ли уже активного диалога
        existing = await db.get_active_conversation(
            initiator_session_id, target.session_id
        )
        if existing:
            continue  # Уже есть диалог

        # Проверить статус в Admin API
        admin_info = await admin_api.get_session(target.session_id)
        if admin_info.get("status") == 1:
            continue  # Нельзя начинать DM

        valid_targets.append(target)

    if not valid_targets:
        return None

    # 4. Выбрать с учётом персон и интересов
    return await select_best_match(initiator, valid_targets)
```

---

#### Изменения в БД

```sql
-- Новый тип аккаунта
ALTER TABLE accounts ADD COLUMN account_type TEXT DEFAULT 'warmup';
-- 'warmup' = прогрев, 'helper' = вспомогательный

-- Ограничения вспомогательных
ALTER TABLE accounts ADD COLUMN can_initiate_dm BOOLEAN DEFAULT TRUE;
-- FALSE для helper аккаунтов

-- Связи между аккаунтами (кто с кем общается)
CREATE TABLE account_relationships (
    id INTEGER PRIMARY KEY,
    account_id_1 INTEGER NOT NULL,
    account_id_2 INTEGER NOT NULL,
    relationship_type TEXT,  -- 'friend', 'acquaintance', 'group_member'
    established_at TIMESTAMP,
    last_interaction_at TIMESTAMP,
    interaction_count INTEGER DEFAULT 0,
    common_groups TEXT,  -- JSON список общих групп
    FOREIGN KEY (account_id_1) REFERENCES accounts(id),
    FOREIGN KEY (account_id_2) REFERENCES accounts(id),
    UNIQUE(account_id_1, account_id_2)
);
```

#### API для синхронизации с Admin API

```python
# scheduler.py - добавить в sync_with_admin_api()

async def sync_helper_accounts(self):
    """Синхронизация вспомогательных аккаунтов из Admin API"""

    # 1. Получить список заспамленных аккаунтов
    spamblocked = await self.admin_api.get_spamblocked_sessions()

    for session in spamblocked:
        # 2. Проверить есть ли уже в БД
        existing = await self.db.get_account_by_session_id(session.id)

        if not existing:
            # 3. Добавить как helper
            await self.db.add_account(
                session_id=session.id,
                phone_number=session.phone,
                account_type='helper',
                can_initiate_dm=False,
                is_active=True,
                # Не участвует в стандартном прогреве
                warmup_stage=0,
            )

            # 4. Сгенерировать персону
            persona = await self.persona_agent.generate_persona(
                country=session.country,
                phone_number=session.phone
            )
            await self.db.save_persona(account_id, persona)

    logger.info(f"Synced {len(spamblocked)} helper accounts")
```

#### Тестирование

- [ ] Unit: синхронизация helper аккаунтов
- [ ] Integration: добавление в БД с правильными флагами
- [ ] API: endpoint для ручного добавления helpers

---

### 1.2 ЛС диалоги между ботами

**Цель:** Прогрев-аккаунты ведут переписки с helper-аккаунтами

#### Архитектура диалогов

```
┌─────────────────────────────────────────────────────────────┐
│                    WARMUP АККАУНТ                           │
│                    (инициатор)                              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ 1. Выбирает helper для диалога
                         │ 2. Отправляет первое сообщение
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    HELPER АККАУНТ                           │
│                    (отвечающий)                             │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ 3. Получает сообщение
                         │ 4. Генерирует ответ через LLM
                         │ 5. Отправляет ответ
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              CONVERSATION ENGINE                            │
│  • Координирует диалог                                      │
│  • Следит за очередностью                                   │
│  • Управляет темпом (паузы)                                 │
│  • Решает когда завершить                                   │
└─────────────────────────────────────────────────────────────┘
```

#### Новая таблица для диалогов

```sql
CREATE TABLE private_conversations (
    id INTEGER PRIMARY KEY,

    -- Участники
    initiator_account_id INTEGER NOT NULL,
    responder_account_id INTEGER NOT NULL,

    -- Telegram IDs для общения
    initiator_session_id TEXT NOT NULL,
    responder_session_id TEXT NOT NULL,

    -- Контекст начала диалога
    conversation_starter TEXT,  -- Причина начала диалога
    common_context TEXT,        -- Общий чат/интерес

    -- Тема и состояние
    current_topic TEXT,
    topics_discussed TEXT,      -- JSON массив обсуждённых тем

    -- Тайминги
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_message_at TIMESTAMP,
    next_response_after TIMESTAMP,  -- Когда можно отвечать

    -- Счётчики
    message_count INTEGER DEFAULT 0,
    initiator_messages INTEGER DEFAULT 0,
    responder_messages INTEGER DEFAULT 0,

    -- Состояние
    status TEXT DEFAULT 'active',  -- active, paused, cooling_down, ended
    end_reason TEXT,               -- natural, timeout, forced

    -- Метаданные
    quality_score REAL,            -- Оценка качества диалога (0-1)

    FOREIGN KEY (initiator_account_id) REFERENCES accounts(id),
    FOREIGN KEY (responder_account_id) REFERENCES accounts(id),
    UNIQUE(initiator_account_id, responder_account_id)
);

-- История сообщений в диалогах (для контекста LLM)
CREATE TABLE conversation_messages (
    id INTEGER PRIMARY KEY,
    conversation_id INTEGER NOT NULL,
    sender_account_id INTEGER NOT NULL,
    message_text TEXT NOT NULL,
    message_type TEXT DEFAULT 'text',  -- text, sticker, voice, photo
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    telegram_message_id INTEGER,

    FOREIGN KEY (conversation_id) REFERENCES private_conversations(id),
    FOREIGN KEY (sender_account_id) REFERENCES accounts(id)
);

CREATE INDEX idx_conv_messages ON conversation_messages(conversation_id, sent_at);
```

#### Новое действие: start_private_conversation

```python
# executor.py

async def _start_private_conversation(self, session_id: str, params: dict) -> dict:
    """Начать личный диалог с другим ботом"""

    target_session_id = params.get("target_session_id")
    starter_message = params.get("message")

    # 1. Проверить что target - наш бот
    target_account = await self.db.get_account_by_session_id(target_session_id)
    if not target_account:
        return {"error": "Target not found in our pool"}

    # 2. Проверить нет ли уже активного диалога
    existing = await self.db.get_active_conversation(session_id, target_session_id)
    if existing:
        return {"error": "Conversation already exists", "conversation_id": existing.id}

    # 3. Отправить сообщение через Telegram
    result = await self.telegram_client.send_message(
        session_id=session_id,
        peer=target_session_id,
        text=starter_message
    )

    if result.get("error"):
        return {"error": result["error"]}

    # 4. Создать запись о диалоге
    my_account = await self.db.get_account_by_session_id(session_id)
    conversation_id = await self.db.create_conversation(
        initiator_account_id=my_account.id,
        responder_account_id=target_account.id,
        initiator_session_id=session_id,
        responder_session_id=target_session_id,
        conversation_starter=starter_message,
        common_context=params.get("context"),
    )

    # 5. Сохранить первое сообщение
    await self.db.save_conversation_message(
        conversation_id=conversation_id,
        sender_account_id=my_account.id,
        message_text=starter_message,
        telegram_message_id=result.get("message_id")
    )

    # 6. Запланировать ответ от helper (через scheduler)
    response_delay = random.uniform(60, 300)  # 1-5 минут
    await self.db.update_conversation(
        conversation_id,
        next_response_after=datetime.now() + timedelta(seconds=response_delay)
    )

    return {
        "success": True,
        "conversation_id": conversation_id,
        "message_sent": starter_message,
        "response_expected_in": response_delay
    }
```

#### LLM: Генерация стартера диалога

```python
# conversation_agent.py (НОВЫЙ ФАЙЛ)

CONVERSATION_STARTER_PROMPT = """
Ты — {my_persona.generated_name}, {my_persona.age} лет, {my_persona.occupation}.
Твой стиль общения: {my_persona.communication_style}

Ты хочешь начать переписку с человеком:
- Имя: {their_persona.generated_name}
- Возраст: {their_persona.age}
- Профессия: {their_persona.occupation}
- Интересы: {their_persona.interests}

ОБЩИЙ КОНТЕКСТ (как вы могли познакомиться):
{common_context}

ТВОЯ ЗАДАЧА:
Напиши ПЕРВОЕ сообщение для начала диалога.

ПРАВИЛА:
1. Сообщение должно быть естественным поводом написать
2. Не представляйся формально ("Привет, я Иван")
3. Можно:
   - Сослаться на общий чат/интерес
   - Задать вопрос по теме интересов собеседника
   - Поделиться чем-то релевантным
4. Длина: 1-3 предложения
5. Тон: дружелюбный, неформальный

ПРИМЕРЫ ХОРОШИХ СТАРТЕРОВ:
- "Привет! Видел тебя в чате про крипту, ты там писал про стейкинг. Сам думаю попробовать, есть опыт?"
- "О, ты тоже из Питера? Как там погода сейчас?"
- "Привет! Случайно заметил твой коммент про Python, сам учу сейчас. Давно в этом?"

ВЕРНИ ТОЛЬКО ТЕКСТ СООБЩЕНИЯ:
"""

class ConversationAgent:
    def __init__(self, llm_client):
        self.llm = llm_client

    async def generate_conversation_starter(
        self,
        my_persona: dict,
        their_persona: dict,
        common_context: str = None
    ) -> str:
        """Генерация первого сообщения для начала диалога"""

        # Если нет общего контекста - найти общие интересы
        if not common_context:
            common_interests = set(my_persona.get("interests", [])) & \
                              set(their_persona.get("interests", []))
            if common_interests:
                common_context = f"Общие интересы: {', '.join(common_interests)}"
            else:
                common_context = "Случайное знакомство в Telegram"

        prompt = CONVERSATION_STARTER_PROMPT.format(
            my_persona=my_persona,
            their_persona=their_persona,
            common_context=common_context
        )

        response = await self.llm.generate(
            prompt=prompt,
            temperature=0.9,
            max_tokens=100
        )

        # Валидация
        validated = await self._validate_starter(response)
        return validated

    async def _validate_starter(self, text: str) -> str:
        """Проверка стартера на адекватность"""

        # Убрать кавычки если есть
        text = text.strip().strip('"\'')

        # Проверки
        if len(text) < 5:
            return None
        if len(text) > 300:
            text = text[:300]

        # Проверить на спам-слова
        spam_patterns = ['заработок', 'инвестиц', 'бесплатно', 'акция', 'скидк']
        if any(p in text.lower() for p in spam_patterns):
            return None

        return text
```

#### LLM: Генерация ответа в диалоге

```python
CONVERSATION_RESPONSE_PROMPT = """
Ты — {my_persona.generated_name}, {my_persona.age} лет, {my_persona.occupation}.
Характер: {my_persona.personality_traits}
Стиль общения: {my_persona.communication_style}

ИСТОРИЯ ПЕРЕПИСКИ:
{conversation_history}

СОБЕСЕДНИК:
{their_persona.generated_name}, {their_persona.age} лет, {their_persona.occupation}

ТЕКУЩАЯ ТЕМА: {current_topic}

ТВОЯ ЗАДАЧА:
Напиши ответ на последнее сообщение.

ПРАВИЛА:
1. Отвечай как живой человек в мессенджере
2. Учитывай контекст всей переписки
3. Можешь:
   - Отвечать на вопросы
   - Задавать свои вопросы
   - Делиться мнением/опытом
   - Использовать эмодзи (умеренно)
   - Шутить если уместно
4. Длина: 1-4 предложения
5. НЕ НАДО:
   - Писать слишком формально
   - Использовать канцелярит
   - Повторять то что уже говорил
   - Резко менять тему

ФОРМАТ ОТВЕТА:
Просто текст сообщения. Если хочешь отправить:
- Стикер: [STICKER:категория] (happy, sad, ok, lol, etc)
- Голосовое: [VOICE:текст который сказать]

ОТВЕТ:
"""

async def generate_conversation_response(
    self,
    my_persona: dict,
    their_persona: dict,
    conversation_history: list,
    current_topic: str = None
) -> dict:
    """Генерация ответа в диалоге"""

    # Форматируем историю
    history_text = self._format_conversation_history(conversation_history)

    # Определяем текущую тему если не задана
    if not current_topic:
        current_topic = await self._extract_topic(conversation_history)

    prompt = CONVERSATION_RESPONSE_PROMPT.format(
        my_persona=my_persona,
        their_persona=their_persona,
        conversation_history=history_text,
        current_topic=current_topic
    )

    response = await self.llm.generate(
        prompt=prompt,
        temperature=0.85,
        max_tokens=150
    )

    # Парсим ответ
    return self._parse_response(response)

def _parse_response(self, response: str) -> dict:
    """Парсинг ответа LLM"""

    result = {"type": "text", "content": response}

    # Проверяем на стикер
    if "[STICKER:" in response:
        match = re.search(r'\[STICKER:(\w+)\]', response)
        if match:
            result = {"type": "sticker", "category": match.group(1)}

    # Проверяем на голосовое
    elif "[VOICE:" in response:
        match = re.search(r'\[VOICE:(.+?)\]', response)
        if match:
            result = {"type": "voice", "content": match.group(1)}

    else:
        # Обычный текст - валидируем
        result["content"] = response.strip().strip('"\'')

    return result

def _format_conversation_history(self, messages: list) -> str:
    """Форматирование истории для промпта"""

    lines = []
    for msg in messages[-15:]:  # Последние 15 сообщений
        sender = "Ты" if msg.is_mine else msg.sender_name
        lines.append(f"{sender}: {msg.text}")

    return "\n".join(lines)
```

#### Conversation Engine (координатор диалогов)

```python
# conversation_engine.py (НОВЫЙ ФАЙЛ)

class ConversationEngine:
    """
    Координатор диалогов между ботами.
    Запускается из scheduler, управляет всеми активными диалогами.
    """

    def __init__(self, db, telegram_client, conversation_agent):
        self.db = db
        self.telegram = telegram_client
        self.agent = conversation_agent

    async def process_pending_responses(self):
        """Обработать все диалоги где пора отвечать"""

        # 1. Получить диалоги где пора отвечать
        pending = await self.db.get_conversations_needing_response()

        for conversation in pending:
            try:
                await self._process_conversation(conversation)
            except Exception as e:
                logger.error(f"Error processing conversation {conversation.id}: {e}")

    async def _process_conversation(self, conversation):
        """Обработать один диалог"""

        # 1. Определить кто должен отвечать
        last_message = await self.db.get_last_conversation_message(conversation.id)

        if last_message.sender_account_id == conversation.initiator_account_id:
            # Последнее от инициатора -> отвечает responder
            responder_id = conversation.responder_account_id
            responder_session = conversation.responder_session_id
        else:
            # Последнее от responder -> отвечает initiator
            responder_id = conversation.initiator_account_id
            responder_session = conversation.initiator_session_id

        # 2. Проверить не пора ли заканчивать диалог
        if await self._should_end_conversation(conversation):
            await self._end_conversation(conversation, responder_session)
            return

        # 3. Загрузить персоны
        my_account = await self.db.get_account_by_id(responder_id)
        my_persona = await self.db.get_persona(responder_id)

        other_id = conversation.initiator_account_id \
            if responder_id == conversation.responder_account_id \
            else conversation.responder_account_id
        their_persona = await self.db.get_persona(other_id)

        # 4. Загрузить историю
        history = await self.db.get_conversation_messages(conversation.id)

        # 5. Сгенерировать ответ
        response = await self.agent.generate_conversation_response(
            my_persona=my_persona,
            their_persona=their_persona,
            conversation_history=history,
            current_topic=conversation.current_topic
        )

        if not response or not response.get("content"):
            logger.warning(f"Empty response for conversation {conversation.id}")
            return

        # 6. Отправить ответ
        peer_session = conversation.initiator_session_id \
            if responder_id == conversation.responder_account_id \
            else conversation.responder_session_id

        if response["type"] == "text":
            result = await self.telegram.send_message(
                session_id=responder_session,
                peer=peer_session,
                text=response["content"]
            )
        elif response["type"] == "sticker":
            result = await self._send_sticker(responder_session, peer_session, response["category"])
        elif response["type"] == "voice":
            result = await self._send_voice(responder_session, peer_session, response["content"])

        if result.get("error"):
            logger.error(f"Failed to send message: {result['error']}")
            return

        # 7. Сохранить сообщение
        await self.db.save_conversation_message(
            conversation_id=conversation.id,
            sender_account_id=responder_id,
            message_text=response.get("content", f"[{response['type']}]"),
            message_type=response["type"],
            telegram_message_id=result.get("message_id")
        )

        # 8. Обновить диалог
        next_delay = self._calculate_next_response_delay(conversation)
        await self.db.update_conversation(
            conversation.id,
            message_count=conversation.message_count + 1,
            last_message_at=datetime.now(),
            next_response_after=datetime.now() + timedelta(seconds=next_delay)
        )

    def _calculate_next_response_delay(self, conversation) -> int:
        """Рассчитать задержку до следующего ответа"""

        # Базовая задержка: 1-5 минут
        base_delay = random.uniform(60, 300)

        # Чем дольше диалог, тем больше паузы
        if conversation.message_count > 10:
            base_delay *= 1.5
        if conversation.message_count > 20:
            base_delay *= 2

        # Иногда большие паузы (человек занят)
        if random.random() < 0.1:
            base_delay += random.uniform(600, 1800)  # +10-30 минут

        return int(base_delay)

    async def _should_end_conversation(self, conversation) -> bool:
        """Определить пора ли заканчивать диалог"""

        # Слишком много сообщений
        if conversation.message_count >= 30:
            return True

        # Диалог идёт слишком долго
        age = datetime.now() - conversation.started_at
        if age.total_seconds() > 48 * 3600:  # 48 часов
            return True

        # Вероятностное завершение после 15 сообщений
        if conversation.message_count > 15 and random.random() < 0.2:
            return True

        return False

    async def _end_conversation(self, conversation, session_id: str):
        """Завершить диалог естественно"""

        # Сгенерировать прощание
        my_persona = await self.db.get_persona_by_session(session_id)

        closing = await self.agent.generate_closing_message(my_persona)

        # Отправить
        peer_session = conversation.initiator_session_id \
            if session_id == conversation.responder_session_id \
            else conversation.responder_session_id

        await self.telegram.send_message(
            session_id=session_id,
            peer=peer_session,
            text=closing
        )

        # Обновить статус
        await self.db.update_conversation(
            conversation.id,
            status='ended',
            end_reason='natural'
        )
```

#### Тестирование ЛС диалогов

```python
# tests/test_private_conversations.py

class TestPrivateConversations:

    async def test_start_conversation(self):
        """Тест начала диалога"""
        # 1. Создать warmup и helper аккаунты
        # 2. Вызвать start_private_conversation
        # 3. Проверить что сообщение отправлено
        # 4. Проверить запись в БД

    async def test_response_generation(self):
        """Тест генерации ответов"""
        # 1. Создать диалог с историей
        # 2. Вызвать generate_conversation_response
        # 3. Проверить что ответ релевантен
        # 4. Проверить что ответ не повторяется

    async def test_conversation_flow(self):
        """Тест полного цикла диалога"""
        # 1. Начать диалог
        # 2. Обменяться 5-10 сообщениями
        # 3. Проверить естественность пауз
        # 4. Завершить диалог

    async def test_helper_cannot_initiate(self):
        """Тест что helper не может начать диалог"""
        # 1. Попробовать начать диалог от helper
        # 2. Проверить что получили ошибку
```

---

### 1.3 Приватные группы ботов

**Цель:** Боты создают приватные группы и общаются в них

#### Зачем нужны приватные группы?

1. **Тренировка групповых диалогов** — учимся общаться в группах до выхода в реальные
2. **Создание истории** — у аккаунтов появляются группы в которых они состоят
3. **Социальные связи** — боты знакомятся через группы
4. **Реалистичность** — у людей есть приватные группы с друзьями

#### Типы приватных групп

```
┌─────────────────────────────────────────────────────────────┐
│  ТИПЫ ПРИВАТНЫХ ГРУПП                                       │
├─────────────────────────────────────────────────────────────┤
│  1. ТЕМАТИЧЕСКАЯ ГРУППА                                     │
│     • 3-8 участников с общим интересом                      │
│     • Обсуждение темы (крипта, IT, кино и т.д.)            │
│     • Умеренная активность                                  │
│                                                             │
│  2. ГРУППА ДРУЗЕЙ                                           │
│     • 3-5 участников                                        │
│     • Общение на разные темы                                │
│     • Более неформальное общение                            │
│                                                             │
│  3. РАБОЧАЯ ГРУППА                                          │
│     • 2-4 участника                                         │
│     • Обсуждение "проекта"                                  │
│     • Деловой стиль                                         │
└─────────────────────────────────────────────────────────────┘
```

#### Новые таблицы

```sql
-- Приватные группы ботов
CREATE TABLE bot_groups (
    id INTEGER PRIMARY KEY,

    -- Telegram данные
    telegram_chat_id INTEGER,
    telegram_invite_link TEXT,
    group_title TEXT NOT NULL,
    group_description TEXT,

    -- Тип и тема
    group_type TEXT NOT NULL,  -- thematic, friends, work
    topic TEXT,                -- Основная тема обсуждения

    -- Создатель
    creator_account_id INTEGER NOT NULL,

    -- Состояние
    status TEXT DEFAULT 'active',  -- active, archived
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP,

    -- Счётчики
    member_count INTEGER DEFAULT 1,
    message_count INTEGER DEFAULT 0,

    FOREIGN KEY (creator_account_id) REFERENCES accounts(id)
);

-- Участники групп
CREATE TABLE bot_group_members (
    id INTEGER PRIMARY KEY,
    group_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,

    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_message_at TIMESTAMP,
    message_count INTEGER DEFAULT 0,

    role TEXT DEFAULT 'member',  -- admin, member

    FOREIGN KEY (group_id) REFERENCES bot_groups(id),
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    UNIQUE(group_id, account_id)
);

-- Сообщения в группах (для контекста)
CREATE TABLE bot_group_messages (
    id INTEGER PRIMARY KEY,
    group_id INTEGER NOT NULL,
    sender_account_id INTEGER NOT NULL,

    message_text TEXT,
    message_type TEXT DEFAULT 'text',
    reply_to_message_id INTEGER,

    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    telegram_message_id INTEGER,

    FOREIGN KEY (group_id) REFERENCES bot_groups(id),
    FOREIGN KEY (sender_account_id) REFERENCES accounts(id)
);

CREATE INDEX idx_group_messages ON bot_group_messages(group_id, sent_at);
```

#### Создание группы

```python
# executor.py

async def _create_bot_group(self, session_id: str, params: dict) -> dict:
    """Создать приватную группу с другими ботами"""

    group_title = params.get("title")
    group_type = params.get("type", "friends")  # thematic, friends, work
    topic = params.get("topic")
    member_session_ids = params.get("members", [])

    # 1. Создать группу в Telegram
    result = await self.telegram_client.create_group(
        session_id=session_id,
        title=group_title,
        user_ids=member_session_ids  # Добавить участников сразу
    )

    if result.get("error"):
        return {"error": result["error"]}

    telegram_chat_id = result.get("chat_id")
    invite_link = result.get("invite_link")

    # 2. Сохранить в БД
    my_account = await self.db.get_account_by_session_id(session_id)

    group_id = await self.db.create_bot_group(
        telegram_chat_id=telegram_chat_id,
        telegram_invite_link=invite_link,
        group_title=group_title,
        group_type=group_type,
        topic=topic,
        creator_account_id=my_account.id
    )

    # 3. Добавить создателя как админа
    await self.db.add_group_member(
        group_id=group_id,
        account_id=my_account.id,
        role='admin'
    )

    # 4. Добавить остальных участников
    for member_session_id in member_session_ids:
        member_account = await self.db.get_account_by_session_id(member_session_id)
        if member_account:
            await self.db.add_group_member(
                group_id=group_id,
                account_id=member_account.id,
                role='member'
            )

    return {
        "success": True,
        "group_id": group_id,
        "telegram_chat_id": telegram_chat_id,
        "members_added": len(member_session_ids) + 1
    }
```

#### Генерация сообщений в группе

```python
GROUP_MESSAGE_PROMPT = """
Ты — {my_persona.generated_name}, участник группы "{group_title}".

ТВОЙ ПРОФИЛЬ:
- Возраст: {my_persona.age}
- Профессия: {my_persona.occupation}
- Интересы: {my_persona.interests}
- Стиль общения: {my_persona.communication_style}

ТЕМА ГРУППЫ: {group_topic}
ТИП ГРУППЫ: {group_type}

ДРУГИЕ УЧАСТНИКИ:
{other_members}

ПОСЛЕДНИЕ СООБЩЕНИЯ:
{recent_messages}

ТВОЯ ЗАДАЧА:
Напиши сообщение в группу.

ПРАВИЛА:
1. Учитывай тему группы и контекст разговора
2. Можешь:
   - Ответить на чьё-то сообщение (укажи @имя)
   - Задать вопрос группе
   - Поделиться мнением/информацией
   - Пошутить если уместно
3. Длина: 1-4 предложения
4. Стиль зависит от типа группы:
   - friends: неформально, можно шутить
   - thematic: по теме, экспертно
   - work: деловой, по существу

ОТВЕТ (только текст):
"""

async def generate_group_message(
    self,
    my_persona: dict,
    group: BotGroup,
    other_members: list,
    recent_messages: list
) -> str:
    """Генерация сообщения для группы"""

    # Форматируем участников
    members_text = "\n".join([
        f"- {m.name}, {m.age} лет, {m.occupation}"
        for m in other_members
    ])

    # Форматируем последние сообщения
    messages_text = "\n".join([
        f"{m.sender_name}: {m.text}"
        for m in recent_messages[-20:]
    ])

    prompt = GROUP_MESSAGE_PROMPT.format(
        my_persona=my_persona,
        group_title=group.group_title,
        group_topic=group.topic,
        group_type=group.group_type,
        other_members=members_text,
        recent_messages=messages_text
    )

    response = await self.llm.generate(
        prompt=prompt,
        temperature=0.9,
        max_tokens=150
    )

    return response.strip().strip('"\'')
```

#### Group Engine (координатор групп)

```python
# group_engine.py (НОВЫЙ ФАЙЛ)

class GroupEngine:
    """
    Координатор активности в приватных группах ботов.
    """

    async def process_group_activity(self):
        """Обработать активность во всех группах"""

        active_groups = await self.db.get_active_bot_groups()

        for group in active_groups:
            # Определить кто должен написать
            next_sender = await self._select_next_sender(group)

            if next_sender and await self._should_send_message(group, next_sender):
                await self._send_group_message(group, next_sender)

    async def _select_next_sender(self, group: BotGroup) -> Optional[int]:
        """Выбрать кто следующий напишет в группу"""

        members = await self.db.get_group_members(group.id)

        # Исключить того кто писал последним
        last_message = await self.db.get_last_group_message(group.id)
        eligible = [m for m in members if m.account_id != last_message.sender_account_id]

        if not eligible:
            return None

        # Взвешенный выбор - кто давно не писал, тот вероятнее
        weights = []
        for member in eligible:
            time_since_last = (datetime.now() - (member.last_message_at or group.created_at)).total_seconds()
            weight = min(time_since_last / 3600, 10)  # Макс вес через 10 часов
            weights.append(weight)

        return random.choices(eligible, weights=weights, k=1)[0].account_id

    async def _should_send_message(self, group: BotGroup, account_id: int) -> bool:
        """Определить нужно ли отправлять сообщение"""

        # Проверить время с последнего сообщения в группе
        last_message = await self.db.get_last_group_message(group.id)
        if last_message:
            time_since_last = (datetime.now() - last_message.sent_at).total_seconds()

            # Минимум 5 минут между сообщениями
            if time_since_last < 300:
                return False

        # Вероятность зависит от времени
        probability = min(time_since_last / 3600, 0.8)  # Макс 80% через час

        return random.random() < probability

    async def _send_group_message(self, group: BotGroup, account_id: int):
        """Отправить сообщение в группу"""

        account = await self.db.get_account_by_id(account_id)
        persona = await self.db.get_persona(account_id)

        # Получить других участников
        members = await self.db.get_group_members(group.id)
        other_personas = [
            await self.db.get_persona(m.account_id)
            for m in members if m.account_id != account_id
        ]

        # Получить историю
        messages = await self.db.get_group_messages(group.id, limit=30)

        # Сгенерировать сообщение
        text = await self.agent.generate_group_message(
            my_persona=persona,
            group=group,
            other_members=other_personas,
            recent_messages=messages
        )

        if not text:
            return

        # Отправить
        result = await self.telegram.send_message(
            session_id=account.session_id,
            peer=group.telegram_chat_id,
            text=text
        )

        if result.get("error"):
            logger.error(f"Failed to send group message: {result['error']}")
            return

        # Сохранить
        await self.db.save_group_message(
            group_id=group.id,
            sender_account_id=account_id,
            message_text=text,
            telegram_message_id=result.get("message_id")
        )

        # Обновить статистику
        await self.db.update_group(
            group.id,
            last_activity_at=datetime.now(),
            message_count=group.message_count + 1
        )
```

#### Тестирование групп

```python
# tests/test_bot_groups.py

class TestBotGroups:

    async def test_create_group(self):
        """Тест создания группы"""
        # 1. Создать группу с 3 участниками
        # 2. Проверить что группа создана в Telegram
        # 3. Проверить записи в БД

    async def test_group_conversation(self):
        """Тест общения в группе"""
        # 1. Создать группу
        # 2. Запустить GroupEngine
        # 3. Проверить что участники пишут по очереди
        # 4. Проверить релевантность сообщений

    async def test_member_selection(self):
        """Тест выбора следующего отправителя"""
        # 1. Симулировать историю сообщений
        # 2. Проверить что выбор справедливый
        # 3. Проверить что последний писавший не выбирается
```

---

### 1.4 Интеграция в Scheduler

```python
# scheduler.py

class WarmupScheduler:
    def __init__(self, ...):
        ...
        self.conversation_engine = ConversationEngine(...)
        self.group_engine = GroupEngine(...)

    async def scheduler_loop(self):
        """Основной цикл планировщика"""

        while self.is_running:
            try:
                # Стандартный прогрев
                await self._process_warmup_accounts()

                # НОВОЕ: Обработка личных диалогов
                await self.conversation_engine.process_pending_responses()

                # НОВОЕ: Обработка активности в группах
                await self.group_engine.process_group_activity()

                # НОВОЕ: Создание новых диалогов/групп
                await self._initiate_new_social_activities()

            except Exception as e:
                logger.error(f"Scheduler error: {e}")

            await asyncio.sleep(60)  # Проверка каждую минуту

    async def _initiate_new_social_activities(self):
        """Инициировать новые социальные активности"""

        # 1. Найти аккаунты без активных диалогов
        lonely_accounts = await self.db.get_accounts_without_conversations(
            min_stage=3,  # Только после 3 дня прогрева
            max_conversations=2  # У кого меньше 2 диалогов
        )

        for account in lonely_accounts[:5]:  # Максимум 5 новых диалогов за цикл
            # Выбрать helper для диалога
            helper = await self._select_conversation_partner(account)
            if helper:
                await self._start_new_conversation(account, helper)

        # 2. Создавать новые группы (редко)
        if random.random() < 0.05:  # 5% шанс за цикл
            await self._create_new_bot_group()
```

---

### Тестирование Фазы 1

#### Чек-лист (ОБНОВЛЕНО 2026-01-08)

```
HELPER АККАУНТЫ:
[x] Синхронизация с Admin API (status check)
[x] Флаги can_initiate_dm работают
[ ] Персоны генерируются для helpers (используются существующие)

ЛИЧНЫЕ ДИАЛОГИ:
[x] Warmup может начать диалог с другим warmup
[x] Аккаунты со status=1 блокируются от получения DM
[x] Сообщения отправляются корректно (через import_contact + send_dm)
[x] История сохраняется в private_conversations
[x] Паузы между сообщениями естественные (30-600 сек)
[x] Диалоги завершаются естественно (после 15-30 сообщений)
[x] LLM генерирует релевантные ответы (DeepSeek)

ПРИВАТНЫЕ ГРУППЫ:
[ ] Группы создаются в Telegram (ФАЗА 1.3 - следующий шаг)
[ ] Участники добавляются
[ ] Сообщения отправляются
[ ] Очередность отправителей справедливая
[ ] Сообщения по теме группы

ИНТЕГРАЦИЯ:
[x] ConversationEngine работает в scheduler
[ ] GroupEngine работает в scheduler (не реализован)
[x] Нет конфликтов с основным прогревом
[x] Логирование корректное
```

---

## Фаза 2: Реальные групповые чаты

> **Внимание:** Начинать только после успешного завершения Фазы 1!

### 2.1 Поиск тематических чатов

После того как боты научились общаться между собой, можно выпускать в реальные чаты.

```python
# search_agent.py - расширение

async def find_public_group_chats(self, persona: dict) -> list:
    """Поиск публичных групповых чатов по интересам"""

    queries = self._generate_group_search_queries(persona)
    # Примеры: "python чат telegram", "криптовалюты обсуждение"

    groups = []

    # 1. Поиск через Google
    for query in queries[:3]:
        results = await self.google_search(f"{query} telegram группа")
        groups.extend(self._extract_telegram_links(results))

    # 2. Поиск через Telegram каталоги
    # @TGStat_Bot, комьюнити-каталоги

    # 3. Фильтрация - только группы (не каналы)
    verified_groups = []
    for group in groups:
        info = await self.telegram_client.get_chat_info(group)
        if info.get("type") in ["group", "supergroup"]:
            verified_groups.append({
                "username": group,
                "title": info.get("title"),
                "member_count": info.get("member_count"),
                "type": info.get("type")
            })

    # 4. Оценка релевантности через LLM
    return await self._rank_by_relevance(verified_groups, persona)
```

### 2.2 Анализ контекста перед ответом

```python
async def analyze_chat_before_responding(
    self,
    session_id: str,
    chat_id: int,
    persona: dict
) -> dict:
    """Анализ чата перед тем как отвечать"""

    # 1. Получить последние сообщения
    messages = await self.telegram.get_chat_history(session_id, chat_id, limit=50)

    # 2. Анализ через LLM
    analysis = await self.llm.analyze(f"""
    Проанализируй этот групповой чат:

    СООБЩЕНИЯ:
    {self._format_messages(messages)}

    ПЕРСОНА КОТОРАЯ ХОЧЕТ ОТВЕТИТЬ:
    {persona}

    ОТВЕТЬ:
    1. О чём сейчас говорят? (тема)
    2. Какой тон общения? (формальный/неформальный)
    3. Есть ли вопрос на который можно ответить?
    4. Уместно ли сейчас вступить в разговор?
    5. Если да - какой тип ответа подойдёт?

    JSON:
    """)

    return json.loads(analysis)
```

### 2.3-2.4 (подробности см. в предыдущей версии плана)

---

## Фаза 3: Улучшение естественности

### 3.1 Паттерны времени активности

(см. предыдущую версию плана)

### 3.2 Stories, стикеры, голосовые

(см. предыдущую версию плана)

### 3.3 Эмоциональные реакции

(см. предыдущую версию плана)

---

## Фаза 4: Тестирование и мониторинг

### Структура тестов

```
tests/
├── unit/
│   ├── test_conversation_agent.py
│   ├── test_conversation_engine.py
│   ├── test_group_engine.py
│   └── test_validators.py
├── integration/
│   ├── test_private_conversations.py
│   ├── test_bot_groups.py
│   └── test_real_chat_participation.py
├── behavior/
│   ├── test_conversation_quality.py
│   ├── test_timing_patterns.py
│   └── test_message_relevance.py
└── safety/
    ├── test_content_filtering.py
    └── test_spam_prevention.py
```

### Mock для тестирования

```python
class TelegramMock:
    """Mock Telegram API для тестов без реального Telegram"""

    def __init__(self):
        self.messages = {}  # chat_id -> [messages]
        self.groups = {}

    async def send_message(self, session_id, peer, text):
        if peer not in self.messages:
            self.messages[peer] = []

        msg_id = len(self.messages[peer]) + 1
        self.messages[peer].append({
            "id": msg_id,
            "from": session_id,
            "text": text,
            "date": datetime.now()
        })

        return {"ok": True, "message_id": msg_id}

    async def get_chat_history(self, session_id, chat_id, limit):
        return self.messages.get(chat_id, [])[-limit:]
```

---

## Приоритеты реализации (ОБНОВЛЕНО)

### Высокий приоритет (СНАЧАЛА)

1. **Вспомогательные аккаунты** — синхронизация helpers из Admin API
2. **ЛС диалоги между ботами** — ConversationEngine
3. **Приватные группы ботов** — GroupEngine
4. **Валидация сообщений** — проверка перед отправкой

### Средний приоритет (ПОТОМ)

5. **Реальные групповые чаты** — поиск и участие
6. **Паттерны времени** — реалистичное распределение
7. **Stories** — просмотр и реакции

### Низкий приоритет

8. **Голосовые/стикеры** — требует интеграции
9. **Опечатки** — мелкий штрих

---

## Следующие шаги

1. **Добавить миграции БД** — новые таблицы для диалогов и групп
2. **Реализовать синхронизацию helpers** — интеграция с Admin API
3. **Создать ConversationAgent** — LLM для генерации диалогов
4. **Создать ConversationEngine** — координатор диалогов
5. **Написать тесты** — до начала реализации
6. **Тестовый запуск** — 5-10 аккаунтов

---

## Открытые вопросы

1. **Admin API endpoint** — какой именно endpoint для спамблок аккаунтов?
2. **Лимиты диалогов** — сколько активных диалогов на аккаунт?
3. **Размер групп** — оптимальное количество участников?
4. **Темы групп** — какие темы приоритетны?
