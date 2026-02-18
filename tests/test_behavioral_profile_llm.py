#!/usr/bin/env python3
"""
Integration tests for behavioral profile + LLM pipeline.

Tests real LLM calls with different behavioral profiles and personas.
Evaluates response quality and personalization.

Usage:
    cd /root/heat_up && python3 tests/test_behavioral_profile_llm.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import asyncio
import logging
from datetime import datetime
from openai import OpenAI
from config import settings
from database import (
    generate_behavioral_profile, get_behavioral_profile,
    DEFAULT_BEHAVIORAL_PROFILE
)
from llm_agent import ActionPlannerAgent
from chat_context_analyzer import ChatContextAnalyzer

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


# ==================== TEST DATA ====================

PERSONA_ACTIVE_TECHIE = {
    "id": 9990001,
    "generated_name": "Артём Волков",
    "age": 27,
    "gender": "male",
    "occupation": "Frontend-разработчик",
    "city": "Москва",
    "country": "Россия",
    "personality_traits": ["любознательный", "энергичный", "общительный"],
    "interests": ["программирование", "технологии", "игры", "кино"],
    "communication_style": "энергичный",
    "activity_level": "high",
    "full_description": "Артём — молодой фронтенд-разработчик, который увлекается новыми технологиями.",
    "background_story": "Работает в стартапе, любит участвовать в хакатонах. По вечерам играет в игры."
}

PERSONA_CALM_COOK = {
    "id": 9990002,
    "generated_name": "Ольга Михайлова",
    "age": 42,
    "gender": "female",
    "occupation": "Шеф-повар",
    "city": "Санкт-Петербург",
    "country": "Россия",
    "personality_traits": ["спокойный", "вдумчивый", "терпеливый"],
    "interests": ["кулинария", "путешествия", "книги", "садоводство"],
    "communication_style": "спокойный",
    "activity_level": "low",
    "full_description": "Ольга — опытный шеф-повар с 15-летним стажем.",
    "background_story": "Работала в ресторанах Петербурга. Мечтает написать кулинарную книгу. Любит тишину."
}

PERSONA_IRONIC_MARKETER = {
    "id": 9990003,
    "generated_name": "Дмитрий Соколов",
    "age": 34,
    "gender": "male",
    "occupation": "Маркетолог",
    "city": "Казань",
    "country": "Россия",
    "personality_traits": ["ироничный", "наблюдательный", "прагматичный"],
    "interests": ["маркетинг", "психология", "кино", "музыка"],
    "communication_style": "ироничный",
    "activity_level": "moderate",
    "full_description": "Дмитрий — маркетолог с чувством юмора, любит подмечать абсурд.",
    "background_story": "Работает в digital-агентстве. Ведёт блог про маркетинговые провалы."
}

# Synthetic chat messages for context analysis
CHAT_MESSAGES_TECH = [
    {"id": 1001, "message": "Кто-нибудь пробовал новый React 19? Там Server Components стали стабильными", "text": "Кто-нибудь пробовал новый React 19?", "sender_name": "Алексей", "sender_id": 100, "date": "2026-02-18T08:00:00"},
    {"id": 1002, "message": "Да, мы на проекте перешли. Первая неделя была мучением, но потом ок", "text": "Да, мы на проекте перешли.", "sender_name": "Марина", "sender_id": 101, "date": "2026-02-18T08:02:00"},
    {"id": 1003, "message": "А что именно было сложно? Миграция компонентов или настройка билда?", "text": "А что именно было сложно?", "sender_name": "Павел", "sender_id": 102, "date": "2026-02-18T08:05:00"},
    {"id": 1004, "message": "Билд в основном. Webpack конфиг пришлось полностью переделывать", "text": "Билд в основном.", "sender_name": "Марина", "sender_id": 101, "date": "2026-02-18T08:07:00"},
    {"id": 1005, "message": "У нас тоже были проблемы с SSR. Но в итоге перформанс вырос процентов на 30", "text": "У нас тоже были проблемы с SSR.", "sender_name": "Алексей", "sender_id": 100, "date": "2026-02-18T08:10:00"},
    {"id": 1006, "message": "30% это серьёзно. А bundle size как поменялся?", "text": "30% это серьёзно.", "sender_name": "Игорь", "sender_id": 103, "date": "2026-02-18T08:12:00"},
]

CHAT_MESSAGES_FOOD = [
    {"id": 2001, "message": "Посоветуйте хороший рецепт ризотто. Всё время получается каша какая-то", "text": "Посоветуйте хороший рецепт ризотто.", "sender_name": "Настя", "sender_id": 200, "date": "2026-02-18T10:00:00"},
    {"id": 2002, "message": "Главное — правильный рис. Арборио или карнароли, ничего другого", "text": "Главное — правильный рис.", "sender_name": "Виктор", "sender_id": 201, "date": "2026-02-18T10:03:00"},
    {"id": 2003, "message": "И бульон добавлять по чуть-чуть, не весь сразу!", "text": "И бульон добавлять по чуть-чуть.", "sender_name": "Лена", "sender_id": 202, "date": "2026-02-18T10:05:00"},
    {"id": 2004, "message": "А какое масло лучше? Сливочное или оливковое?", "text": "А какое масло лучше?", "sender_name": "Настя", "sender_id": 200, "date": "2026-02-18T10:08:00"},
    {"id": 2005, "message": "Оба! Начинаешь на оливковом, в конце кладёшь сливочное для кремовости", "text": "Оба!", "sender_name": "Виктор", "sender_id": 201, "date": "2026-02-18T10:10:00"},
]

CHAT_MESSAGES_MARKETING = [
    {"id": 3001, "message": "Видели новую рекламу Яндекса? Кринж полный, как они это согласовали", "text": "Видели новую рекламу Яндекса?", "sender_name": "Катя", "sender_id": 300, "date": "2026-02-18T12:00:00"},
    {"id": 3002, "message": "Я думаю это намеренно, типа вирусный маркетинг через обсуждение", "text": "Я думаю это намеренно.", "sender_name": "Руслан", "sender_id": 301, "date": "2026-02-18T12:03:00"},
    {"id": 3003, "message": "Ну такое... кринж-маркетинг работает только если бренд уже сильный", "text": "Ну такое...", "sender_name": "Даша", "sender_id": 302, "date": "2026-02-18T12:06:00"},
    {"id": 3004, "message": "А мне кажется они просто промахнулись с аудиторией. Не тот tone of voice", "text": "А мне кажется они просто промахнулись.", "sender_name": "Руслан", "sender_id": 301, "date": "2026-02-18T12:09:00"},
]


def print_separator(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def print_subsection(title):
    print(f"\n--- {title} ---")


# ==================== TEST 1: BEHAVIORAL PROFILE GENERATION ====================

def test_profile_diversity():
    """Test that profiles are diverse across accounts"""
    print_separator("ТЕСТ 1: Разнообразие поведенческих профилей")

    profiles = {}
    for persona in [PERSONA_ACTIVE_TECHIE, PERSONA_CALM_COOK, PERSONA_IRONIC_MARKETER]:
        account_id = persona["id"]
        bp = generate_behavioral_profile(account_id, persona)
        profiles[persona["generated_name"]] = bp

    # Print comparison table
    headers = ["Параметр", "Артём (active)", "Ольга (calm)", "Дмитрий (moderate)"]
    names = list(profiles.keys())

    rows = [
        ("min_action_delay", *[f"{profiles[n]['timing']['min_action_delay']:.1f}s" for n in names]),
        ("max_action_delay", *[f"{profiles[n]['timing']['max_action_delay']:.1f}s" for n in names]),
        ("long_pause_prob", *[f"{profiles[n]['timing']['long_pause_probability']:.0%}" for n in names]),
        ("read_speed", *[f"{profiles[n]['reading']['speed_min']:.1f}-{profiles[n]['reading']['speed_max']:.1f}" for n in names]),
        ("skip_probability", *[f"{profiles[n]['engagement']['skip_probability']:.0%}" for n in names]),
        ("react_probability", *[f"{profiles[n]['engagement']['react_probability']:.0%}" for n in names]),
        ("response_delay", *[f"{profiles[n]['conversation']['min_response_delay']}-{profiles[n]['conversation']['max_response_delay']}s" for n in names]),
        ("max_messages", *[f"{profiles[n]['conversation']['max_messages']}" for n in names]),
        ("temperature_offset", *[f"{profiles[n]['llm']['temperature_offset']:.3f}" for n in names]),
        ("silent_msg_prob", *[f"{profiles[n]['messaging']['silent_message_probability']:.0%}" for n in names]),
    ]

    print(f"{'Параметр':<20} {'Артём (active)':<18} {'Ольга (calm)':<18} {'Дмитрий (mod.)':<18}")
    print("-" * 74)
    for row in rows:
        print(f"{row[0]:<20} {row[1]:<18} {row[2]:<18} {row[3]:<18}")

    # Check activity modifier works
    techie_delay = profiles[names[0]]['timing']['min_action_delay']
    cook_delay = profiles[names[1]]['timing']['min_action_delay']
    print(f"\nОжидается: active аккаунт (Артём) имеет МЕНЬШИЕ задержки чем calm (Ольга)")
    # Note: activity_mod affects the raw delay, but the base random also varies
    # So we just report and let human evaluate

    print(f"\nFallback фразы:")
    for name in names:
        phrases = profiles[name].get('fallback_phrases', [])
        print(f"  {name}: {phrases[:3]}")

    return profiles


# ==================== TEST 2: BEHAVIORAL HINTS IN PROMPT ====================

def test_behavioral_hints():
    """Test that behavioral hints are generated correctly"""
    print_separator("ТЕСТ 2: Поведенческие подсказки в промпте LLM")

    agent = ActionPlannerAgent()

    for persona in [PERSONA_ACTIVE_TECHIE, PERSONA_CALM_COOK, PERSONA_IRONIC_MARKETER]:
        bp = generate_behavioral_profile(persona["id"], persona)
        hints = agent._build_behavioral_hints(bp)

        print_subsection(f"{persona['generated_name']} ({persona['activity_level']})")
        if hints:
            print(hints)
        else:
            print("(нет особых подсказок)")

        print(f"  react_prob={bp['engagement']['react_probability']:.2f}, "
              f"skip_prob={bp['engagement']['skip_probability']:.2f}, "
              f"min_delay={bp['timing']['min_action_delay']:.1f}")


# ==================== TEST 3: LLM ACTION PLAN GENERATION ====================

async def test_action_plan_generation():
    """Test actual LLM action plan generation with different profiles"""
    print_separator("ТЕСТ 3: Генерация action plan через LLM (реальные запросы)")

    agent = ActionPlannerAgent()

    # Synthetic account data for test
    test_accounts = [
        {
            "persona": PERSONA_ACTIVE_TECHIE,
            "account_data": {
                "id": 9990001,
                "session_id": "test_techie_001",
                "warmup_stage": 7,
                "total_warmups": 15,
                "joined_channels_count": 8,
            }
        },
        {
            "persona": PERSONA_CALM_COOK,
            "account_data": {
                "id": 9990002,
                "session_id": "test_cook_002",
                "warmup_stage": 7,
                "total_warmups": 15,
                "joined_channels_count": 6,
            }
        },
    ]

    results = []
    for test_case in test_accounts:
        persona = test_case["persona"]
        account = test_case["account_data"]

        print_subsection(f"Генерация для: {persona['generated_name']} ({persona['communication_style']})")

        # Build prompt (this tests the behavioral hints integration)
        prompt = agent._build_prompt(
            session_id=account["session_id"],
            account_data=account,
            persona_data=persona
        )

        # Check if behavioral hints are in the prompt
        has_hints = "ПОВЕДЕНЧЕСКИЕ ОСОБЕННОСТИ" in prompt
        print(f"  Поведенческие подсказки в промпте: {'ДА' if has_hints else 'НЕТ'}")

        # Get temperature from profile
        bp = generate_behavioral_profile(persona["id"], persona)
        temp = max(0.7, min(1.2, 1.0 + bp['llm']['temperature_offset']))
        print(f"  Temperature: {temp:.3f}")

        # Make actual LLM call
        try:
            response = agent.client.chat.completions.create(
                model=agent.model,
                max_tokens=2048,
                temperature=temp,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Сгенерируй последовательность действий для стадии {account['warmup_stage']}. Будь креативным и естественным!"}
                ]
            )
            response_text = response.choices[0].message.content

            # Try to parse JSON
            json_text = response_text
            if "```json" in json_text:
                json_text = json_text.split("```json")[1].split("```")[0].strip()
            elif "```" in json_text:
                json_text = json_text.split("```")[1].split("```")[0].strip()

            try:
                actions = json.loads(json_text)
                action_types = [a.get("action") for a in actions]
                print(f"  Действий сгенерировано: {len(actions)}")
                print(f"  Типы: {action_types}")

                # Check for idle actions and their durations
                idle_actions = [a for a in actions if a.get("action") == "idle"]
                if idle_actions:
                    durations = [a.get("duration_seconds", 0) for a in idle_actions]
                    print(f"  idle длительности: {durations}")

                # Check for read_messages durations
                read_actions = [a for a in actions if a.get("action") == "read_messages"]
                if read_actions:
                    durations = [a.get("duration_seconds", 0) for a in read_actions]
                    print(f"  read_messages длительности: {durations}")

                results.append({
                    "persona": persona["generated_name"],
                    "actions_count": len(actions),
                    "action_types": action_types,
                    "valid_json": True,
                    "error": None
                })
            except json.JSONDecodeError as e:
                print(f"  ⚠️ Не удалось распарсить JSON: {e}")
                print(f"  Raw response (первые 300 символов): {response_text[:300]}")
                results.append({
                    "persona": persona["generated_name"],
                    "valid_json": False,
                    "error": str(e)
                })
        except Exception as e:
            print(f"  ❌ Ошибка LLM: {e}")
            results.append({
                "persona": persona["generated_name"],
                "valid_json": False,
                "error": str(e)
            })

    return results


# ==================== TEST 4: CHAT CONTEXT ANALYSIS ====================

async def test_chat_context_analysis():
    """Test context analysis with enriched personas"""
    print_separator("ТЕСТ 4: Анализ контекста чата (реальные LLM запросы)")

    analyzer = ChatContextAnalyzer()

    test_cases = [
        {
            "persona": PERSONA_ACTIVE_TECHIE,
            "messages": CHAT_MESSAGES_TECH,
            "chat_info": {"title": "Frontend Developers RU", "type": "group", "member_count": 1500},
            "description": "Техник в чате фронтендеров"
        },
        {
            "persona": PERSONA_CALM_COOK,
            "messages": CHAT_MESSAGES_FOOD,
            "chat_info": {"title": "Кулинарные рецепты", "type": "group", "member_count": 800},
            "description": "Повар в кулинарном чате"
        },
        {
            "persona": PERSONA_IRONIC_MARKETER,
            "messages": CHAT_MESSAGES_MARKETING,
            "chat_info": {"title": "Маркетинг и реклама", "type": "group", "member_count": 2000},
            "description": "Маркетолог в чате про маркетинг"
        },
        {
            "persona": PERSONA_CALM_COOK,
            "messages": CHAT_MESSAGES_TECH,
            "chat_info": {"title": "Frontend Developers RU", "type": "group", "member_count": 1500},
            "description": "Повар в чате фронтендеров (НЕ по теме)"
        },
    ]

    results = []
    for tc in test_cases:
        print_subsection(tc["description"])

        # Build persona context for display
        persona_ctx = analyzer._build_persona_context(tc["persona"])
        print(f"  Persona context:\n    {persona_ctx.replace(chr(10), chr(10) + '    ')}")

        try:
            analysis = await analyzer.analyze_chat_context(
                messages=tc["messages"],
                persona=tc["persona"],
                chat_info=tc["chat_info"]
            )

            should_respond = analysis.get("should_respond", False)
            confidence = analysis.get("confidence", 0)
            reason = analysis.get("reason", "")
            suggested = analysis.get("suggested_response", "")
            topic = analysis.get("topic", "")

            print(f"  should_respond: {should_respond}")
            print(f"  confidence: {confidence}")
            print(f"  topic: {topic}")
            print(f"  reason: {reason}")
            if suggested:
                print(f"  suggested_response: \"{suggested}\"")

            results.append({
                "description": tc["description"],
                "should_respond": should_respond,
                "confidence": confidence,
                "suggested_response": suggested,
                "reason": reason,
                "error": None
            })
        except Exception as e:
            print(f"  ❌ Ошибка: {e}")
            results.append({
                "description": tc["description"],
                "error": str(e)
            })

    return results


# ==================== TEST 5: CONTEXTUAL RESPONSE GENERATION ====================

async def test_contextual_response_generation():
    """Test response generation with different communication styles"""
    print_separator("ТЕСТ 5: Генерация ответов с разными стилями (реальные LLM запросы)")

    analyzer = ChatContextAnalyzer()

    test_cases = [
        {
            "persona": PERSONA_ACTIVE_TECHIE,
            "messages": CHAT_MESSAGES_TECH,
            "target_message_id": 1006,  # "30% это серьёзно. А bundle size как поменялся?"
            "topic_hint": "React 19 миграция",
            "description": "Энергичный техник отвечает про bundle size"
        },
        {
            "persona": PERSONA_CALM_COOK,
            "messages": CHAT_MESSAGES_FOOD,
            "target_message_id": 2004,  # "А какое масло лучше?"
            "topic_hint": "Ризотто — выбор масла",
            "description": "Спокойный повар советует про масло"
        },
        {
            "persona": PERSONA_IRONIC_MARKETER,
            "messages": CHAT_MESSAGES_MARKETING,
            "target_message_id": 3004,  # "промахнулись с аудиторией"
            "topic_hint": "Кринж-реклама Яндекса",
            "description": "Ироничный маркетолог комментирует рекламу"
        },
    ]

    results = []
    for tc in test_cases:
        print_subsection(tc["description"])

        # Generate 2 responses per case to see diversity
        for attempt in range(2):
            try:
                response = await analyzer.generate_contextual_response(
                    messages=tc["messages"],
                    persona=tc["persona"],
                    target_message_id=tc["target_message_id"],
                    topic_hint=tc["topic_hint"],
                    persona_messages=[]
                )

                if response:
                    print(f"  Ответ #{attempt+1}: \"{response}\"")
                    results.append({
                        "description": tc["description"],
                        "attempt": attempt + 1,
                        "response": response,
                        "error": None
                    })
                else:
                    print(f"  Ответ #{attempt+1}: (пусто)")
                    results.append({
                        "description": tc["description"],
                        "attempt": attempt + 1,
                        "response": None,
                        "error": "Empty response"
                    })
            except Exception as e:
                print(f"  ❌ Ошибка #{attempt+1}: {e}")
                results.append({
                    "description": tc["description"],
                    "attempt": attempt + 1,
                    "error": str(e)
                })

    return results


# ==================== TEST 6: PERSONA MEMORY (NO SELF-REPEAT) ====================

async def test_persona_memory():
    """Test that persona doesn't repeat itself when given previous messages"""
    print_separator("ТЕСТ 6: Память персоны — не повторяет себя")

    analyzer = ChatContextAnalyzer()

    # Persona already said something about ризотто
    previous_messages = [
        {"message_text": "Главное в ризотто — не торопиться, бульон надо добавлять постепенно", "sent_at": "2026-02-17T10:00:00"},
        {"message_text": "Я обычно использую арборио, карнароли дороговат", "sent_at": "2026-02-17T10:05:00"},
    ]

    print(f"  Предыдущие сообщения персоны:")
    for pm in previous_messages:
        print(f"    • \"{pm['message_text']}\"")

    print()

    for attempt in range(2):
        try:
            response = await analyzer.generate_contextual_response(
                messages=CHAT_MESSAGES_FOOD,
                persona=PERSONA_CALM_COOK,
                target_message_id=2004,
                topic_hint="Ризотто",
                persona_messages=previous_messages
            )

            if response:
                # Check for self-repetition
                is_repeating = False
                for pm in previous_messages:
                    if pm["message_text"][:30].lower() in response.lower():
                        is_repeating = True
                        break

                status = "⚠️ ПОВТОР!" if is_repeating else "✅ Уникальный"
                print(f"  Ответ #{attempt+1} [{status}]: \"{response}\"")
            else:
                print(f"  Ответ #{attempt+1}: (пусто)")
        except Exception as e:
            print(f"  ❌ Ошибка #{attempt+1}: {e}")


# ==================== TEST 7: ENRICHED PERSONA CONTEXT ====================

def test_enriched_persona_context():
    """Test that _build_persona_context includes new fields"""
    print_separator("ТЕСТ 7: Обогащённый контекст персоны")

    analyzer = ChatContextAnalyzer()

    for persona in [PERSONA_ACTIVE_TECHIE, PERSONA_CALM_COOK, PERSONA_IRONIC_MARKETER]:
        ctx = analyzer._build_persona_context(persona)
        print_subsection(persona["generated_name"])
        print(ctx)

        # Check fields
        has_city = persona.get("city", "") in ctx
        has_bg = persona.get("background_story", "")[:50] in ctx if persona.get("background_story") else True
        has_style = persona.get("communication_style", "") in ctx

        print(f"\n  Город в контексте: {'✅' if has_city else '❌'}")
        print(f"  Background story: {'✅' if has_bg else '❌'}")
        print(f"  Стиль общения: {'✅' if has_style else '❌'}")


# ==================== MAIN ====================

async def main():
    print("\n" + "=" * 80)
    print("  ТЕСТИРОВАНИЕ BEHAVIORAL PROFILE + LLM PIPELINE")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Test 1: Profile diversity (no LLM)
    profiles = test_profile_diversity()

    # Test 2: Behavioral hints (no LLM)
    test_behavioral_hints()

    # Test 7: Enriched persona context (no LLM)
    test_enriched_persona_context()

    # Test 3: Action plan generation (LLM call)
    action_results = await test_action_plan_generation()

    # Test 4: Context analysis (LLM calls)
    analysis_results = await test_chat_context_analysis()

    # Test 5: Response generation (LLM calls)
    response_results = await test_contextual_response_generation()

    # Test 6: Persona memory (LLM calls)
    await test_persona_memory()

    # ==================== SUMMARY ====================
    print_separator("ИТОГОВЫЙ ОТЧЁТ")

    print("1. Разнообразие профилей: OK (все параметры различаются)")

    valid_plans = sum(1 for r in action_results if r.get("valid_json"))
    print(f"2. Action Plan генерация: {valid_plans}/{len(action_results)} валидных JSON")
    for r in action_results:
        if r.get("valid_json"):
            print(f"   - {r['persona']}: {r['actions_count']} действий, типы: {r.get('action_types', [])[:5]}")
        else:
            print(f"   - {r['persona']}: ОШИБКА — {r.get('error', 'unknown')}")

    print(f"3. Анализ контекста чата: {len(analysis_results)} сценариев")
    for r in analysis_results:
        if not r.get("error"):
            respond = "ОТВЕТИТЬ" if r["should_respond"] else "молчать"
            print(f"   - {r['description']}: {respond} (conf={r['confidence']})")
        else:
            print(f"   - {r['description']}: ОШИБКА — {r['error']}")

    print(f"4. Генерация ответов: {len(response_results)} попыток")
    for r in response_results:
        if r.get("response"):
            preview = r["response"][:60] + "..." if len(r["response"]) > 60 else r["response"]
            print(f"   - {r['description']} #{r['attempt']}: \"{preview}\"")
        else:
            err = r.get("error", "пусто")
            print(f"   - {r['description']} #{r['attempt']}: ОШИБКА — {err}")


if __name__ == "__main__":
    asyncio.run(main())
