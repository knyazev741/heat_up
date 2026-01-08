#!/usr/bin/env python3
"""
Script to fix chat_type in discovered_chats table.

The search agent was storing incorrect types (defaulting to 'group').
This script resolves each joined chat via Telegram API and updates
the database with the correct type (supergroup/channel).
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram_client import TelegramAPIClient
import sqlite3
from datetime import datetime


async def fix_chat_types():
    """Fix chat_type for all joined chats."""
    client = TelegramAPIClient()
    conn = sqlite3.connect('data/sessions.db')
    cur = conn.cursor()

    # Get all joined chats with their sessions
    cur.execute('''
        SELECT DISTINCT dc.id, dc.chat_username, dc.chat_type, a.session_id
        FROM discovered_chats dc
        JOIN accounts a ON dc.account_id = a.id
        WHERE dc.is_joined = 1
        AND dc.chat_username IS NOT NULL
        AND a.is_active = 1
    ''')

    chats = cur.fetchall()
    print(f"Checking {len(chats)} joined chats...\n")

    stats = {
        'supergroup': 0,
        'channel': 0,
        'group': 0,
        'errors': 0,
        'unchanged': 0
    }

    for i, (chat_id, chat_username, old_type, session_id) in enumerate(chats):
        if i > 0 and i % 20 == 0:
            print(f"Progress: {i}/{len(chats)}...")

        try:
            resolve = await client.resolve_peer(session_id, chat_username)
            if resolve.get('success'):
                chat_data = resolve.get('chat_data', {})

                # Determine real type
                if chat_data.get('megagroup'):
                    new_type = 'supergroup'
                elif chat_data.get('broadcast'):
                    new_type = 'channel'
                else:
                    new_type = 'group'

                # Update if different
                if new_type != old_type:
                    cur.execute(
                        "UPDATE discovered_chats SET chat_type = ? WHERE id = ?",
                        (new_type, chat_id)
                    )
                    print(f"  {chat_username}: {old_type} -> {new_type}")
                    stats[new_type] += 1
                else:
                    stats['unchanged'] += 1
            else:
                stats['errors'] += 1
        except Exception as e:
            stats['errors'] += 1

    conn.commit()
    conn.close()

    print(f"\n=== RESULTS ===")
    print(f"Updated to supergroup: {stats['supergroup']}")
    print(f"Updated to channel: {stats['channel']}")
    print(f"Updated to group: {stats['group']}")
    print(f"Unchanged: {stats['unchanged']}")
    print(f"Errors: {stats['errors']}")

    # Show final statistics
    conn = sqlite3.connect('data/sessions.db')
    cur = conn.cursor()
    cur.execute('''
        SELECT chat_type, COUNT(*)
        FROM discovered_chats
        WHERE is_joined = 1
        GROUP BY chat_type
    ''')
    print(f"\n=== FINAL STATS ===")
    for r in cur.fetchall():
        print(f"  {r[0] or 'unknown'}: {r[1]}")
    conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("  FIX CHAT TYPES IN DATABASE")
    print("=" * 60)
    print()
    asyncio.run(fix_chat_types())
    print("\nDone!")
