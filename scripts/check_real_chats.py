#!/usr/bin/env python3
"""
Script to check real chat participation results.
Shows what groups were found, which are real supergroups,
and tests the context analyzer on actual messages.
"""

import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chat_context_analyzer import ChatContextAnalyzer
from telegram_client import TelegramAPIClient
import sqlite3


def get_db_stats():
    """Get database statistics for Phase 2."""
    conn = sqlite3.connect('data/sessions.db')
    cur = conn.cursor()

    print("=" * 60)
    print("  PHASE 2 DATABASE STATISTICS")
    print("=" * 60)

    # Joined chats by type
    print("\n📊 Joined chats by type:")
    cur.execute('''
        SELECT chat_type, COUNT(*)
        FROM discovered_chats
        WHERE is_joined = 1
        GROUP BY chat_type
    ''')
    for r in cur.fetchall():
        print(f"  {r[0] or 'unknown'}: {r[1]}")

    # Real chat participation
    cur.execute('SELECT COUNT(*) FROM real_chat_participation')
    print(f"\n📝 Real chat participation records: {cur.fetchone()[0]}")

    cur.execute('SELECT COUNT(*) FROM real_chat_messages')
    print(f"📨 Cached messages: {cur.fetchone()[0]}")

    # Action history
    cur.execute('''
        SELECT action_type, COUNT(*) as cnt
        FROM session_history
        WHERE timestamp > datetime('now', '-7 days')
        GROUP BY action_type
        ORDER BY cnt DESC
        LIMIT 10
    ''')
    print("\n📈 Action stats (last 7 days):")
    for r in cur.fetchall():
        print(f"  {r[0]}: {r[1]}")

    # reply_in_chat attempts
    print("\n🎯 reply_in_chat attempts:")
    cur.execute('''
        SELECT sh.session_id, sh.action_data, sh.timestamp
        FROM session_history sh
        WHERE sh.action_type = 'reply_in_chat'
        ORDER BY sh.timestamp DESC
        LIMIT 5
    ''')
    rows = cur.fetchall()
    if rows:
        for r in rows:
            try:
                data = json.loads(r[1]) if r[1] else {}
                chat = data.get('chat_username', '?')
                print(f"  {r[2]} | Session {r[0]} -> {chat}")
            except:
                print(f"  {r[2]} | Session {r[0]}")
    else:
        print("  No reply_in_chat actions recorded yet")

    conn.close()


async def find_real_supergroups():
    """Find actual supergroups (not channels) from joined chats."""
    client = TelegramAPIClient()
    conn = sqlite3.connect('data/sessions.db')
    cur = conn.cursor()

    print("\n" + "=" * 60)
    print("  FINDING REAL SUPERGROUPS")
    print("=" * 60)

    # Get some joined chats
    cur.execute('''
        SELECT DISTINCT dc.chat_username, dc.account_id, a.session_id, dc.chat_title
        FROM discovered_chats dc
        JOIN accounts a ON dc.account_id = a.id
        WHERE dc.is_joined = 1 AND dc.chat_username IS NOT NULL
        LIMIT 30
    ''')

    chats = cur.fetchall()
    supergroups = []

    print(f"\nChecking {len(chats)} chats...\n")

    for chat_username, account_id, session_id, title in chats:
        try:
            resolve = await client.resolve_peer(session_id, chat_username)
            if resolve.get('success'):
                chat_data = resolve.get('chat_data', {})
                is_megagroup = chat_data.get('megagroup', False)
                is_broadcast = chat_data.get('broadcast', False)
                real_title = chat_data.get('title', title or '')[:40]

                if is_megagroup and not is_broadcast:
                    supergroups.append({
                        'username': chat_username,
                        'title': real_title,
                        'session_id': session_id,
                        'account_id': account_id
                    })
                    print(f"  ✅ {chat_username} - {real_title} (SUPERGROUP)")
        except Exception as e:
            pass

    if supergroups:
        print(f"\n🎉 Found {len(supergroups)} real supergroups where we can participate!")
        return supergroups
    else:
        print("\n⚠️ No real supergroups found in checked chats")
        return []

    conn.close()


async def test_context_analyzer(supergroup):
    """Test context analyzer on a real supergroup."""
    client = TelegramAPIClient()
    analyzer = ChatContextAnalyzer()

    chat = supergroup['username']
    session_id = supergroup['session_id']

    print("\n" + "=" * 60)
    print(f"  TESTING CONTEXT ANALYZER ON {chat}")
    print("=" * 60)

    # Resolve
    resolve = await client.resolve_peer(session_id, chat)
    if not resolve.get('success'):
        print(f"Failed to resolve: {resolve.get('error')}")
        return

    # Get input_peer
    input_peer = resolve.get('input_peer')
    if isinstance(input_peer, str):
        input_peer = json.loads(input_peer)

    peer_info = {'input_peer': input_peer}

    result = await client.get_chat_history(
        session_id=session_id,
        peer_info=peer_info,
        limit=15
    )

    if not result.get('success') or not result.get('messages'):
        print(f"Failed to get history: {result.get('error')}")
        return

    messages = result['messages']
    print(f"\n📝 Got {len(messages)} messages:\n")

    for msg in messages[:6]:
        sender = msg.get('sender_name', 'Unknown')
        text = msg.get('text', '')[:80] if msg.get('text') else '[media]'
        print(f"  [{sender}]: {text}")

    # Get persona for this account
    conn = sqlite3.connect('data/sessions.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT generated_name, city, interests, occupation
        FROM personas
        WHERE account_id = ?
    ''', (supergroup['account_id'],))
    row = cur.fetchone()
    conn.close()

    if row:
        interests = json.loads(row[2]) if row[2] else []
        persona = {
            'generated_name': row[0],
            'city': row[1],
            'interests': interests,
            'occupation': row[3]
        }
        print(f"\n👤 Using persona: {persona['generated_name']} ({persona['city']})")
        print(f"   Interests: {', '.join(interests[:3])}")
    else:
        persona = {
            'generated_name': 'Тест Пользователь',
            'city': 'Москва',
            'interests': ['технологии', 'общение'],
            'occupation': 'специалист'
        }
        print(f"\n👤 Using default persona")

    # Analyze
    print(f"\n🔍 Running context analysis...")
    analysis = await analyzer.analyze_chat_context(
        messages=messages,
        persona=persona,
        chat_info={'title': supergroup['title'], 'type': 'supergroup'}
    )

    print(f"\n📊 Analysis Result:")
    print(f"   Should respond: {analysis.get('should_respond')}")
    print(f"   Confidence: {analysis.get('confidence')}")
    print(f"   Topic: {analysis.get('topic')}")
    print(f"   Reason: {analysis.get('reason')}")

    if analysis.get('suggested_response'):
        print(f"\n💬 Suggested response:")
        print(f'   "{analysis.get("suggested_response")}"')

    return analysis


async def main():
    # Get DB stats
    get_db_stats()

    # Find real supergroups
    supergroups = await find_real_supergroups()

    # Test analyzer on first suitable supergroup
    if supergroups:
        # Skip inappropriate chats
        suitable = [sg for sg in supergroups if 'интим' not in sg['title'].lower() and 'ночн' not in sg['title'].lower()]

        if suitable:
            await test_context_analyzer(suitable[0])
        elif supergroups:
            print("\n⚠️ Found supergroups but they are not suitable for testing")
    else:
        print("\n⚠️ No supergroups to test")

    print("\n" + "=" * 60)
    print("  DONE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
