#!/usr/bin/env python3
"""
Test sending a message to a real supergroup.
This verifies that Phase 2 reply_in_chat functionality works end-to-end.
"""

import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chat_context_analyzer import ChatContextAnalyzer
from telegram_client import TelegramAPIClient
from database import (
    get_or_create_chat_participation,
    can_send_message_in_chat,
    increment_chat_messages_sent,
)
import sqlite3


async def test_send_message():
    """Test sending a message to a supergroup."""
    client = TelegramAPIClient()
    analyzer = ChatContextAnalyzer()
    conn = sqlite3.connect('data/sessions.db')
    cur = conn.cursor()

    # Find a suitable supergroup with an eligible account
    print("=" * 60)
    print("  FINDING SUITABLE SUPERGROUP FOR TEST")
    print("=" * 60)

    # Get supergroups with stage 8+ accounts, excluding inappropriate ones
    cur.execute('''
        SELECT
            dc.chat_username,
            dc.chat_title,
            a.id as account_id,
            a.session_id,
            p.generated_name,
            p.city,
            p.interests,
            p.occupation
        FROM discovered_chats dc
        JOIN accounts a ON dc.account_id = a.id
        LEFT JOIN personas p ON a.id = p.account_id
        WHERE dc.is_joined = 1
        AND dc.chat_type = 'supergroup'
        AND a.warmup_stage >= 8
        AND a.is_active = 1
        AND dc.chat_title NOT LIKE '%интим%'
        AND dc.chat_title NOT LIKE '%ночн%'
        AND dc.chat_title NOT LIKE '%18+%'
        ORDER BY RANDOM()
        LIMIT 10
    ''')

    candidates = cur.fetchall()

    if not candidates:
        print("❌ No suitable supergroups found!")
        return False

    print(f"\nFound {len(candidates)} candidates:")
    for c in candidates[:5]:
        print(f"  {c[0]} - {c[1][:40] if c[1] else '?'} | {c[4]} ({c[5]})")

    # Try each candidate until we find one that works
    for chat_username, chat_title, account_id, session_id, persona_name, city, interests_json, occupation in candidates:
        print(f"\n{'=' * 60}")
        print(f"  TESTING: {chat_username}")
        print(f"  Account: {persona_name} ({city}), Session {session_id}")
        print("=" * 60)

        # Check if we can send (not exceeded daily limit)
        if not can_send_message_in_chat(account_id, chat_username):
            print(f"⚠️ Daily limit reached for {chat_username}, skipping...")
            continue

        # Resolve peer
        print(f"\n1️⃣ Resolving peer...")
        resolve = await client.resolve_peer(session_id, chat_username)
        if not resolve.get('success'):
            print(f"❌ Failed to resolve: {resolve.get('error')}")
            continue

        chat_data = resolve.get('chat_data', {})
        if not chat_data.get('megagroup'):
            print(f"⚠️ Not a megagroup, skipping...")
            continue

        print(f"✅ Resolved: {chat_data.get('title')}")

        # Get input_peer
        input_peer = resolve.get('input_peer')
        if isinstance(input_peer, str):
            input_peer = json.loads(input_peer)

        # Fetch messages
        print(f"\n2️⃣ Fetching messages...")
        history = await client.get_chat_history(
            session_id=session_id,
            peer_info={'input_peer': input_peer},
            limit=15
        )

        # Parse raw result - messages are at result['result']['messages']
        raw_result = history.get('result', {})
        raw_messages = raw_result.get('messages', [])
        raw_users = {u['id']: u for u in raw_result.get('users', [])}

        if not raw_messages:
            print(f"❌ No messages found")
            continue

        # Parse messages manually
        messages = []
        for msg in raw_messages:
            if msg.get('_') == 'types.Message' and msg.get('message'):
                from_id = msg.get('from_id', {})
                user_id = from_id.get('user_id') if isinstance(from_id, dict) else None
                user = raw_users.get(user_id, {}) if user_id else {}
                sender = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or 'Anonymous'
                messages.append({
                    'id': msg.get('id'),
                    'sender_name': sender,
                    'text': msg.get('message'),
                    'date': msg.get('date')
                })

        if not messages:
            print(f"❌ No text messages found")
            continue

        print(f"✅ Got {len(messages)} messages:")
        for m in messages[:5]:
            text = m.get('text', '')[:60] if m.get('text') else '[media]'
            print(f"   [{m.get('sender_name', '?')}]: {text}")

        # Parse interests
        try:
            interests = json.loads(interests_json) if interests_json else []
        except:
            interests = []

        persona = {
            'generated_name': persona_name,
            'city': city,
            'interests': interests,
            'occupation': occupation
        }

        # Analyze context
        print(f"\n3️⃣ Analyzing context...")
        analysis = await analyzer.analyze_chat_context(
            messages=messages,
            persona=persona,
            chat_info={'title': chat_title or chat_username, 'type': 'supergroup'}
        )

        print(f"   Should respond: {analysis.get('should_respond')}")
        print(f"   Confidence: {analysis.get('confidence')}")
        print(f"   Topic: {analysis.get('topic')}")
        print(f"   Reason: {analysis.get('reason')}")

        # Generate response if should respond
        if not analysis.get('should_respond'):
            print(f"\n⚠️ Context analyzer decided not to respond. Trying next group...")
            continue

        # Generate contextual response
        print(f"\n4️⃣ Generating response...")
        response_text = await analyzer.generate_contextual_response(
            messages=messages,
            persona=persona,
            topic_hint=analysis.get('topic')
        )

        if not response_text:
            print(f"❌ Failed to generate response")
            continue

        print(f"✅ Generated response:")
        print(f"   \"{response_text}\"")

        # Confirm before sending
        print(f"\n5️⃣ SENDING MESSAGE...")
        print(f"   To: {chat_username} ({chat_title})")
        print(f"   From: {persona_name} (session {session_id})")
        print(f"   Text: {response_text[:100]}...")

        # Send the message
        send_result = await client.send_message(
            session_id=session_id,
            chat_id=chat_username,
            text=response_text
        )

        if send_result.get('error'):
            print(f"\n❌ SEND FAILED: {send_result.get('error')}")
            continue

        print(f"\n✅ MESSAGE SENT SUCCESSFULLY!")
        print(f"   Message ID: {send_result.get('result', {}).get('id', 'unknown')}")

        # Update participation stats
        increment_chat_messages_sent(account_id, chat_username)
        print(f"   Updated participation stats")

        conn.close()
        return True

    print("\n❌ Could not send message to any supergroup")
    conn.close()
    return False


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  PHASE 2 TEST: SEND MESSAGE TO SUPERGROUP")
    print("=" * 60)

    success = asyncio.run(test_send_message())

    print("\n" + "=" * 60)
    if success:
        print("  ✅ TEST PASSED - Message sent successfully!")
    else:
        print("  ❌ TEST FAILED - Could not send message")
    print("=" * 60)
