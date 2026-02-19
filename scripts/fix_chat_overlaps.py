#!/usr/bin/env python3
"""
Исправляет пересечения по чатам среди warmup аккаунтов.
Оставляет только самого первого вступившего, остальные помечаются как not joined.
"""

import sqlite3
import sys
sys.path.insert(0, '/root/heat_up')

from datetime import datetime


def fix_overlaps():
    conn = sqlite3.connect('/root/heat_up/data/sessions.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Находим все пересечения среди активных warmup
    cur.execute('''
        SELECT dc.chat_username, dc.account_id, dc.joined_at, a.session_id
        FROM discovered_chats dc
        JOIN accounts a ON dc.account_id = a.id
        WHERE dc.is_joined = 1
        AND a.account_type = 'warmup'
        AND a.is_active = 1
        AND a.is_frozen = 0
        AND a.is_deleted = 0
        ORDER BY dc.chat_username, dc.joined_at ASC
    ''')

    rows = cur.fetchall()

    # Группируем по чату
    chats = {}
    for row in rows:
        chat = row['chat_username']
        if chat not in chats:
            chats[chat] = []
        chats[chat].append({
            'account_id': row['account_id'],
            'session_id': row['session_id'],
            'joined_at': row['joined_at']
        })

    # Находим чаты с пересечениями
    overlaps = {chat: accounts for chat, accounts in chats.items() if len(accounts) > 1}

    print(f"=== OVERLAPS FOUND: {len(overlaps)} chats ===\n")

    total_fixed = 0
    for chat, accounts in sorted(overlaps.items(), key=lambda x: -len(x[1])):
        print(f"{chat}: {len(accounts)} accounts")

        # Первый остаётся (самый ранний join)
        keeper = accounts[0]
        print(f"  KEEPING: account_id={keeper['account_id']} (session {keeper['session_id']}) joined at {keeper['joined_at']}")

        # Остальные снимаем
        for acc in accounts[1:]:
            print(f"  REMOVING: account_id={acc['account_id']} (session {acc['session_id']})")
            cur.execute('''
                UPDATE discovered_chats
                SET is_joined = 0, joined_at = NULL
                WHERE account_id = ? AND chat_username = ?
            ''', (acc['account_id'], chat))

            # Уменьшаем счётчик joined_channels_count
            cur.execute('''
                UPDATE accounts
                SET joined_channels_count = MAX(0, joined_channels_count - 1)
                WHERE id = ?
            ''', (acc['account_id'],))

            total_fixed += 1
        print()

    conn.commit()
    conn.close()

    print(f"=== TOTAL FIXED: {total_fixed} overlapping joins removed ===")
    return total_fixed


if __name__ == "__main__":
    fix_overlaps()
