#!/usr/bin/env python3
"""
Chat Overlaps Monitor Script

Shows current chat overlaps between warmup accounts.
Does NOT make any changes - the isolation happens automatically
through the new exclusivity checks in scheduler/executor.

Usage:
    python scripts/cleanup_chat_overlaps.py [--verbose]

Options:
    --verbose   Show detailed information about each overlap
"""

import sys
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
from database import DATABASE_PATH, get_db_connection


def find_chat_overlaps(verbose: bool = False) -> list:
    """
    Find chats where multiple warmup accounts are joined.

    Returns:
        List of dicts with overlap info
    """
    overlaps = []

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Find chats with multiple warmup accounts
        cursor.execute("""
            SELECT
                dc.chat_username,
                COUNT(DISTINCT dc.account_id) as warmup_count,
                GROUP_CONCAT(dc.account_id) as account_ids
            FROM discovered_chats dc
            JOIN accounts a ON dc.account_id = a.id
            WHERE dc.is_joined = 1
            AND a.account_type = 'warmup'
            AND a.is_active = 1
            AND a.is_deleted = 0
            GROUP BY dc.chat_username
            HAVING warmup_count > 1
            ORDER BY warmup_count DESC
        """)

        rows = cursor.fetchall()

        for row in rows:
            chat_username = row['chat_username']
            account_ids = [int(x) for x in row['account_ids'].split(',')]

            accounts = []
            if verbose:
                for acc_id in account_ids:
                    cursor.execute("""
                        SELECT
                            a.id,
                            a.session_id,
                            dc.joined_at,
                            COALESCE(rcp.messages_sent, 0) as messages_sent
                        FROM accounts a
                        JOIN discovered_chats dc ON dc.account_id = a.id
                        LEFT JOIN real_chat_participation rcp
                            ON rcp.account_id = a.id AND rcp.chat_username = dc.chat_username
                        WHERE a.id = ?
                        AND dc.chat_username = ?
                    """, (acc_id, chat_username))

                    acc_row = cursor.fetchone()
                    if acc_row:
                        accounts.append({
                            'id': acc_row['id'],
                            'messages_sent': acc_row['messages_sent'],
                            'joined_at': acc_row['joined_at'],
                        })

            overlaps.append({
                'chat_username': chat_username,
                'warmup_count': row['warmup_count'],
                'account_ids': account_ids,
                'accounts': accounts,
            })

    return overlaps


def main():
    parser = argparse.ArgumentParser(description='Monitor chat overlaps between warmup accounts')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed information')
    args = parser.parse_args()

    print("=== Warmup Account Chat Overlap Monitor ===")
    print(f"Database: {DATABASE_PATH}")
    print()
    print("NOTE: This script only SHOWS overlaps. The isolation happens")
    print("automatically through scheduler (accounts will search for new chats).")
    print()

    overlaps = find_chat_overlaps(verbose=args.verbose)

    if not overlaps:
        print("No overlaps found. All chats have at most one warmup account.")
        return 0

    print(f"Found {len(overlaps)} chats with overlapping warmup accounts:")
    print()

    total_affected_accounts = sum(o['warmup_count'] - 1 for o in overlaps)

    for overlap in overlaps:
        chat = overlap['chat_username']
        count = overlap['warmup_count']

        print(f"Chat: {chat}")
        print(f"  Warmup accounts: {count} (IDs: {overlap['account_ids'][:5]}{'...' if len(overlap['account_ids']) > 5 else ''})")

        if args.verbose and overlap['accounts']:
            for acc in overlap['accounts']:
                print(f"    - Account {acc['id']}: {acc.get('messages_sent', 0)} msgs")

        print()

    print("=== Summary ===")
    print(f"Total overlapping chats: {len(overlaps)}")
    print(f"Total accounts affected: {total_affected_accounts}")
    print()
    print("These overlaps will be resolved automatically:")
    print("1. When accounts try to join occupied chats - they will be blocked")
    print("2. When accounts have few available chats - scheduler will search for new ones")
    print("3. Accounts will gradually migrate to exclusive chats")

    return 0


if __name__ == '__main__':
    sys.exit(main())
