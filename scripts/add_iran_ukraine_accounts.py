#!/usr/bin/env python3
"""
Script to find Iranian and Ukrainian accounts with status 0 or 1
from Admin API and add them to warmup.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from admin_api_client import AdminAPIClient
from database import get_account, add_account, get_db_connection
from persona_agent import PersonaAgent
from config import settings
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Countries to search for (Admin API country values)
TARGET_COUNTRIES = ['ir', 'iran', 'ua', 'ukraine']


async def get_all_sessions_by_status(api: AdminAPIClient, status: int) -> list:
    """Fetch all sessions with given status (handles pagination)"""
    all_sessions = []
    skip = 0
    limit = 100

    while True:
        result = await api.get_sessions(
            skip=skip,
            limit=limit,
            status=status,
            deleted=False,
            frozen=False
        )

        items = result.get('items', [])
        total = result.get('total', 0)

        all_sessions.extend(items)

        if len(items) < limit or len(all_sessions) >= total:
            break

        skip += limit

    return all_sessions


def is_target_country(country: str) -> bool:
    """Check if country is Iranian or Ukrainian"""
    if not country:
        return False
    country_lower = country.lower().strip()
    return country_lower in TARGET_COUNTRIES


async def main():
    api = AdminAPIClient()
    persona_agent = PersonaAgent()

    try:
        logger.info("=== Fetching sessions from Admin API ===")

        # Fetch sessions with status 0 and 1
        sessions_status_0 = await get_all_sessions_by_status(api, 0)
        sessions_status_1 = await get_all_sessions_by_status(api, 1)

        logger.info(f"Found {len(sessions_status_0)} sessions with status=0")
        logger.info(f"Found {len(sessions_status_1)} sessions with status=1")

        all_sessions = sessions_status_0 + sessions_status_1

        # Filter by country
        target_sessions = []
        country_stats = {}

        for session in all_sessions:
            country = session.get('country', '')

            # Collect stats
            if country:
                country_stats[country] = country_stats.get(country, 0) + 1

            if is_target_country(country):
                target_sessions.append(session)

        logger.info(f"\n=== Country distribution (status 0 and 1) ===")
        for country, count in sorted(country_stats.items(), key=lambda x: -x[1])[:20]:
            marker = " <-- TARGET" if is_target_country(country) else ""
            logger.info(f"  {country}: {count}{marker}")

        logger.info(f"\n=== Target sessions (Iran/Ukraine) ===")
        logger.info(f"Found {len(target_sessions)} Iranian/Ukrainian sessions")

        if not target_sessions:
            logger.info("No Iranian or Ukrainian sessions found.")
            return

        # Check which are not in warmup yet
        to_add = []
        already_in_warmup = []

        for session in target_sessions:
            session_id = str(session.get('id'))
            existing = get_account(session_id)

            if existing:
                already_in_warmup.append(session)
            else:
                to_add.append(session)

        logger.info(f"\nAlready in warmup: {len(already_in_warmup)}")
        logger.info(f"To be added: {len(to_add)}")

        if already_in_warmup:
            logger.info("\n--- Already in warmup ---")
            for s in already_in_warmup[:10]:
                logger.info(f"  Session {s['id']}: {s.get('country')} status={s.get('status')}")
            if len(already_in_warmup) > 10:
                logger.info(f"  ... and {len(already_in_warmup) - 10} more")

        if to_add:
            logger.info("\n--- Sessions to add ---")
            for s in to_add:
                logger.info(f"  Session {s['id']}: {s.get('phone_number', '?')[-4:]}**** country={s.get('country')} status={s.get('status')}")

        if not to_add:
            logger.info("\nNo new sessions to add.")
            return

        # Check for --yes flag
        auto_confirm = '--yes' in sys.argv or '-y' in sys.argv

        if not auto_confirm:
            # Ask for confirmation
            print(f"\n{'='*50}")
            print(f"Ready to add {len(to_add)} sessions to warmup.")
            confirm = input("Continue? (y/n): ").strip().lower()

            if confirm != 'y':
                logger.info("Cancelled by user.")
                return
        else:
            logger.info(f"\nAuto-confirming addition of {len(to_add)} sessions...")

        # Add sessions to warmup
        added_count = 0
        failed_count = 0

        for session in to_add:
            session_id = str(session.get('id'))
            phone_number = session.get('phone_number', '')
            country = session.get('country', '')

            # Normalize country name
            if country.lower() in ['ir', 'iran']:
                country_normalized = 'Iran'
            elif country.lower() in ['ua', 'ukraine']:
                country_normalized = 'Ukraine'
            else:
                country_normalized = country

            try:
                # Generate persona
                logger.info(f"Generating persona for session {session_id} ({country_normalized})...")
                persona_data = await persona_agent.generate_persona(phone_number, country_normalized)

                # Add to database
                account_id = add_account(
                    session_id=session_id,
                    phone_number=phone_number,
                    country=country_normalized,
                    account_type='warmup',
                    can_initiate_dm=True
                )

                if account_id:
                    # Save persona
                    with get_db_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT OR REPLACE INTO personas
                            (account_id, generated_name, age, occupation, city, country,
                             personality_traits, interests, communication_style,
                             emoji_usage, typical_online_hours, bio_text,
                             created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                    datetime('now'), datetime('now'))
                        """, (
                            account_id,
                            persona_data.get('generated_name', ''),
                            persona_data.get('age', 25),
                            persona_data.get('occupation', ''),
                            persona_data.get('city', ''),
                            persona_data.get('country', country_normalized),
                            persona_data.get('personality_traits', ''),
                            persona_data.get('interests', ''),
                            persona_data.get('communication_style', ''),
                            persona_data.get('emoji_usage', 'moderate'),
                            persona_data.get('typical_online_hours', ''),
                            persona_data.get('bio_text', '')
                        ))
                        conn.commit()

                    logger.info(f"  Added session {session_id} as account {account_id}")
                    added_count += 1
                else:
                    logger.error(f"  Failed to add session {session_id}")
                    failed_count += 1

            except Exception as e:
                logger.error(f"  Error adding session {session_id}: {e}")
                failed_count += 1

        logger.info(f"\n=== Summary ===")
        logger.info(f"Added: {added_count}")
        logger.info(f"Failed: {failed_count}")

    finally:
        await api.close()


if __name__ == "__main__":
    asyncio.run(main())
