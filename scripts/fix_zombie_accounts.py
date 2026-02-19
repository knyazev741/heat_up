"""
Fix Zombie Accounts

Скрипт для одноразовой очистки "зомби" аккаунтов — тех, что удалены/заморожены
в Admin API, но всё ещё помечены как активные в локальной БД.

Использование:
    python3 scripts/fix_zombie_accounts.py [--dry-run]

Flags:
    --dry-run   Только показать расхождения, не менять БД
"""

import sys
import os
import asyncio
import logging
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db_connection
from admin_api_client import AdminAPIClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


async def fix_zombie_accounts(dry_run: bool = False):
    """Check all 'active' warmup accounts against Admin API and fix zombies."""

    # 1. Get all locally active warmup accounts
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, session_id, phone_number, is_frozen, is_deleted
            FROM accounts
            WHERE account_type = 'warmup'
              AND is_active = 1
              AND is_deleted = 0
        """)
        active_accounts = [dict(row) for row in cursor.fetchall()]

    logger.info(f"Found {len(active_accounts)} locally active warmup accounts to verify")

    client = AdminAPIClient()
    zombies_deleted = []
    zombies_frozen = []
    zombies_status1 = []
    not_found = []
    ok_count = 0

    try:
        for acc in active_accounts:
            session_id = acc["session_id"]
            try:
                session = await client.get_session_by_id(int(session_id))
            except Exception as e:
                logger.error(f"  Error checking session {session_id}: {e}")
                continue

            if session is None:
                not_found.append(acc)
                logger.warning(
                    f"  ❓ Session {session_id} ({acc['phone_number']}) NOT FOUND in Admin API"
                )
                continue

            is_deleted = session.get("deleted", False)
            is_frozen = session.get("frozen", False)
            status = session.get("status")

            problems = []
            if is_deleted:
                problems.append("deleted=True")
                zombies_deleted.append(acc)
            if is_frozen:
                problems.append("frozen=True")
                zombies_frozen.append(acc)
            if status == 1:
                problems.append("status=1 (in work)")
                zombies_status1.append(acc)

            if problems:
                logger.warning(
                    f"  🧟 ZOMBIE: session {session_id} ({acc['phone_number']}) — {', '.join(problems)}"
                )
            else:
                ok_count += 1

    finally:
        await client.close()

    # Summary
    logger.info("=" * 60)
    logger.info("SUMMARY:")
    logger.info(f"  Total checked:  {len(active_accounts)}")
    logger.info(f"  OK:             {ok_count}")
    logger.info(f"  Deleted in API: {len(zombies_deleted)}")
    logger.info(f"  Frozen in API:  {len(zombies_frozen)}")
    logger.info(f"  Status=1:       {len(zombies_status1)}")
    logger.info(f"  Not found:      {len(not_found)}")

    if dry_run:
        logger.info("DRY RUN — no changes made to database")
        return

    # Apply fixes
    fixed = 0
    with get_db_connection() as conn:
        cursor = conn.cursor()

        for acc in zombies_deleted:
            cursor.execute(
                "UPDATE accounts SET is_deleted = 1 WHERE session_id = ?",
                (acc["session_id"],)
            )
            fixed += 1

        for acc in zombies_frozen:
            cursor.execute(
                "UPDATE accounts SET is_frozen = 1 WHERE session_id = ?",
                (acc["session_id"],)
            )
            fixed += 1

        # Not-found accounts are likely deleted — mark them
        for acc in not_found:
            cursor.execute(
                "UPDATE accounts SET is_deleted = 1 WHERE session_id = ?",
                (acc["session_id"],)
            )
            fixed += 1

        conn.commit()

    logger.info(f"Fixed {fixed} accounts in local database")


def main():
    parser = argparse.ArgumentParser(description="Fix zombie accounts")
    parser.add_argument("--dry-run", action="store_true", help="Only show mismatches, don't update DB")
    args = parser.parse_args()

    asyncio.run(fix_zombie_accounts(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
