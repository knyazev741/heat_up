#!/usr/bin/env python3
"""
Sync Ukrainian accounts from Admin API to local warmup database.

Usage:
    python scripts/sync_ua_accounts.py [--dry-run]

This script:
1. Fetches UA sessions from Admin API (status=2, not spamblock, not frozen, not deleted)
2. Compares with existing accounts in local DB
3. Adds missing accounts as 'warmup' type with can_initiate_dm=1
"""

import asyncio
import sys
import logging
from pathlib import Path
from datetime import datetime
import json
import random

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from admin_api_client import AdminAPIClient
from database import get_db_connection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def get_ua_sessions_from_api(client: AdminAPIClient) -> list:
    """
    Fetch Ukrainian sessions from Admin API.

    Criteria:
    - country='ukraine'
    - status=0 (new accounts for warmup)
    - spamblock=False
    - frozen=False
    - deleted=False
    """
    all_sessions = []
    skip = 0
    limit = 100

    logger.info("Fetching Ukrainian sessions from Admin API...")

    # First, get total count
    result = await client.get_sessions(
        country='ukraine',  # lowercase as stored in DB
        status=0,  # new accounts for warmup
        spamblock=False,
        frozen=False,
        deleted=False,
        skip=0,
        limit=1
    )
    total = result.get('total', 0)
    logger.info(f"Total Ukrainian sessions in Admin API: {total}")

    # Fetch all pages
    while skip < total:
        result = await client.get_sessions(
            country='ukraine',  # lowercase as stored in DB
            status=0,  # new accounts for warmup
            spamblock=False,
            frozen=False,
            deleted=False,
            skip=skip,
            limit=limit
        )

        items = result.get('items', [])
        if not items:
            break

        all_sessions.extend(items)
        skip += limit

        if skip % 500 == 0:
            logger.info(f"  Fetched {len(all_sessions)} sessions...")

    logger.info(f"Fetched {len(all_sessions)} UA sessions total")
    return all_sessions


def get_existing_session_ids() -> set:
    """Get set of session_ids already in local DB"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT session_id FROM accounts")
        return {row[0] for row in cursor.fetchall()}


def create_persona(cursor, account_id: int, first_name: str, last_name: str):
    """Create a persona for new warmup account"""
    if first_name:
        generated_name = f"{first_name} {last_name}".strip() if last_name else first_name
    else:
        ua_names = [
            "Олексій Петренко", "Марія Іванова", "Дмитро Сидоренко",
            "Анна Козак", "Сергій Новак", "Олена Мороз",
            "Андрій Вовк", "Ольга Соколова", "Микола Лебідь",
            "Ірина Шевченко", "Василь Бойко", "Тетяна Коваль"
        ]
        generated_name = random.choice(ua_names)

    all_interests = [
        "технології", "спорт", "музика", "кіно", "подорожі",
        "книги", "ігри", "кулінарія", "фотографія", "мистецтво"
    ]
    interests = random.sample(all_interests, k=random.randint(2, 4))

    styles = ["дружній", "спокійний", "енергійний", "вдумливий"]

    cursor.execute("""
        INSERT OR IGNORE INTO personas (
            account_id, generated_name, interests, communication_style,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        account_id,
        generated_name,
        json.dumps(interests, ensure_ascii=False),
        random.choice(styles),
        datetime.utcnow().isoformat(),
        datetime.utcnow().isoformat()
    ))


async def sync_ua_accounts(dry_run: bool = False) -> dict:
    """
    Sync Ukrainian accounts from Admin API to local DB.

    Args:
        dry_run: If True, don't make any changes, just report what would be done

    Returns:
        Dict with sync results
    """
    client = AdminAPIClient()

    try:
        # Get UA sessions from API
        ua_sessions = await get_ua_sessions_from_api(client)

        # Get existing session IDs
        existing_ids = get_existing_session_ids()
        logger.info(f"Existing accounts in local DB: {len(existing_ids)}")

        # Find sessions to add
        sessions_to_add = []
        for session in ua_sessions:
            session_id = str(session.get('id'))
            if session_id not in existing_ids:
                sessions_to_add.append(session)

        logger.info(f"Sessions to add: {len(sessions_to_add)}")

        if dry_run:
            logger.info("DRY RUN - no changes will be made")
            for session in sessions_to_add[:10]:  # Show first 10
                logger.info(f"  Would add: {session.get('phone_number')} (ID: {session.get('id')})")
            if len(sessions_to_add) > 10:
                logger.info(f"  ... and {len(sessions_to_add) - 10} more")
            return {
                'success': True,
                'dry_run': True,
                'total_in_api': len(ua_sessions),
                'existing_in_db': len(existing_ids),
                'would_add': len(sessions_to_add),
                'added': 0
            }

        # Add new accounts
        added_count = 0
        with get_db_connection() as conn:
            cursor = conn.cursor()

            for session in sessions_to_add:
                session_id = str(session.get('id'))
                phone = session.get('phone_number', '')
                country = session.get('country', 'UA')
                provider = session.get('provider', '')

                # Insert as warmup account
                cursor.execute("""
                    INSERT INTO accounts (
                        session_id, phone_number, country, provider,
                        warmup_stage, is_active, is_frozen, is_deleted,
                        is_banned, can_initiate_dm, account_type,
                        created_at, min_daily_activity, max_daily_activity
                    ) VALUES (?, ?, ?, ?, 1, 1, 0, 0, 0, 1, 'warmup', ?, 3, 6)
                """, (session_id, phone, country, provider, datetime.utcnow().isoformat()))

                account_id = cursor.lastrowid

                # Create persona
                first_name = session.get('first_name', '') or ''
                last_name = session.get('last_name', '') or ''
                create_persona(cursor, account_id, first_name, last_name)

                added_count += 1

                if added_count % 50 == 0:
                    logger.info(f"  Added {added_count} accounts...")

            conn.commit()

        logger.info(f"Successfully added {added_count} UA accounts")

        return {
            'success': True,
            'dry_run': False,
            'total_in_api': len(ua_sessions),
            'existing_in_db': len(existing_ids),
            'would_add': len(sessions_to_add),
            'added': added_count
        }

    except Exception as e:
        logger.error(f"Error syncing UA accounts: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        await client.close()


async def main():
    dry_run = '--dry-run' in sys.argv

    logger.info("=" * 60)
    logger.info("Ukrainian Accounts Sync")
    logger.info("=" * 60)

    result = await sync_ua_accounts(dry_run=dry_run)

    logger.info("=" * 60)
    logger.info("Results:")
    for key, value in result.items():
        logger.info(f"  {key}: {value}")
    logger.info("=" * 60)

    return result


if __name__ == "__main__":
    asyncio.run(main())
