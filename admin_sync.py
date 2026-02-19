"""
Admin API Status Sync Module

This module provides functions to sync session statuses from Admin API
that can be imported and used in other modules (like scheduler).
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from admin_api_client import AdminAPIClient
from database import get_db_connection

logger = logging.getLogger(__name__)


async def sync_session_statuses() -> Dict[str, Any]:
    """
    Sync session statuses from Admin API to local DB
    
    Returns:
        Dict with sync results:
        {
            'success': bool,
            'frozen_count': int,
            'deleted_count': int,
            'banned_forever_count': int,
            'error': Optional[str]
        }
    """
    
    client = AdminAPIClient()
    
    try:
        logger.info("🔄 Starting automatic sync from Admin API...")
        
        # Sync frozen sessions
        frozen_ids = await _sync_frozen_sessions(client)
        
        # Sync deleted sessions
        deleted_ids = await _sync_deleted_sessions(client)

        # Verify active accounts individually (compensate for Admin API filter bug)
        verified_deleted, verified_frozen = await _verify_active_accounts(client)
        deleted_ids.update(verified_deleted)
        frozen_ids.update(verified_frozen)

        # Sync banned forever sessions
        banned_forever_ids = await _sync_banned_forever_sessions(client)
        
        result = {
            'success': True,
            'frozen_count': len(frozen_ids),
            'deleted_count': len(deleted_ids),
            'banned_forever_count': len(banned_forever_ids),
            'total_problematic': len(frozen_ids) + len(deleted_ids) + len(banned_forever_ids),
            'error': None
        }
        
        logger.info(
            f"✅ Sync completed: {result['frozen_count']} frozen, "
            f"{result['deleted_count']} deleted, "
            f"{result['banned_forever_count']} banned forever"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error during sync: {e}", exc_info=True)
        return {
            'success': False,
            'frozen_count': 0,
            'deleted_count': 0,
            'banned_forever_count': 0,
            'total_problematic': 0,
            'error': str(e)
        }
    finally:
        await client.close()


async def _sync_frozen_sessions(client: AdminAPIClient) -> set:
    """Sync frozen sessions and record new freezes to journal"""
    logger.debug("Syncing frozen sessions...")

    # Get currently frozen sessions BEFORE resetting
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT session_id FROM accounts WHERE is_frozen = 1")
        previously_frozen = {row[0] for row in cursor.fetchall()}

        # Reset all frozen flags
        cursor.execute("UPDATE accounts SET is_frozen = 0")
        conn.commit()

    result = await client.get_sessions(frozen=True, limit=100)
    total = result.get('total', 0)
    frozen_ids = set()
    frozen_api_data = {}  # Store Admin API data for journal

    skip = 0
    limit = 100

    while skip < total:
        result = await client.get_sessions(frozen=True, skip=skip, limit=limit)
        items = result.get('items', [])

        if not items:
            break

        for session in items:
            session_id = str(session.get('id'))
            frozen_ids.add(session_id)
            # Store API data for potential journal entry
            frozen_api_data[session_id] = {
                "phone_number": session.get('phone_number'),
                "status": session.get('status'),
                "frozen": session.get('frozen'),
                "ban_date": session.get('ban_date'),
                "country": session.get('country'),
                "provider": session.get('provider')
            }

        skip += limit

    if frozen_ids:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join(['?' for _ in frozen_ids])
            cursor.execute(
                f"UPDATE accounts SET is_frozen = 1 WHERE session_id IN ({placeholders})",
                list(frozen_ids)
            )
            conn.commit()

    # Record new freezes to journal (only warmup accounts)
    newly_frozen = frozen_ids - previously_frozen
    if newly_frozen:
        # Filter to only warmup accounts with warmup history
        with get_db_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join(['?' for _ in newly_frozen])
            cursor.execute(
                f"""SELECT session_id FROM accounts
                    WHERE session_id IN ({placeholders})
                    AND account_type = 'warmup' AND total_warmups > 0""",
                list(newly_frozen)
            )
            warmup_frozen = {row[0] for row in cursor.fetchall()}

        if warmup_frozen:
            logger.warning(f"Detected {len(warmup_frozen)} newly frozen WARMUP accounts!")
            try:
                from freeze_journal import record_freeze_event
                for session_id in warmup_frozen:
                    record_freeze_event(
                        session_id,
                        freeze_source="admin_api_sync",
                        admin_api_data=frozen_api_data.get(session_id)
                    )
            except Exception as e:
                logger.error(f"Error recording freeze events: {e}")

    return frozen_ids


async def _sync_deleted_sessions(client: AdminAPIClient) -> set:
    """Sync deleted sessions"""
    logger.debug("Syncing deleted sessions...")
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE accounts SET is_deleted = 0")
        conn.commit()
    
    result = await client.get_sessions(deleted=True, limit=100)
    total = result.get('total', 0)
    deleted_ids = set()
    
    skip = 0
    limit = 100
    
    while skip < total:
        result = await client.get_sessions(deleted=True, skip=skip, limit=limit)
        items = result.get('items', [])
        
        if not items:
            break
        
        for session in items:
            session_id = str(session.get('id'))
            deleted_ids.add(session_id)
        
        skip += limit
        
        # Only log every 1000 to avoid spam
        if skip % 1000 == 0 and skip > 0:
            logger.debug(f"  Fetched {len(deleted_ids)} deleted sessions...")
    
    if deleted_ids:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            chunk_size = 900
            deleted_list = list(deleted_ids)
            
            for i in range(0, len(deleted_list), chunk_size):
                chunk = deleted_list[i:i+chunk_size]
                placeholders = ','.join(['?' for _ in chunk])
                cursor.execute(
                    f"UPDATE accounts SET is_deleted = 1 WHERE session_id IN ({placeholders})",
                    chunk
                )
            
            conn.commit()
    
    return deleted_ids


async def _sync_banned_forever_sessions(client: AdminAPIClient) -> set:
    """Sync banned forever sessions"""
    logger.debug("Syncing banned forever sessions...")
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE accounts SET unban_date = '2099-01-01' WHERE is_banned = 1")
        conn.commit()
    
    result = await client.get_sessions(spamblock=True, limit=100)
    total = result.get('total', 0)
    banned_forever_ids = set()
    
    skip = 0
    limit = 100
    
    while skip < total:
        result = await client.get_sessions(spamblock=True, skip=skip, limit=limit)
        items = result.get('items', [])
        
        if not items:
            break
        
        for session in items:
            if session.get('spamblock') and not session.get('unban_date'):
                session_id = str(session.get('id'))
                banned_forever_ids.add(session_id)
        
        skip += limit
    
    if banned_forever_ids:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join(['?' for _ in banned_forever_ids])
            cursor.execute(
                f"UPDATE accounts SET is_banned = 1, unban_date = NULL WHERE session_id IN ({placeholders})",
                list(banned_forever_ids)
            )
            conn.commit()
    
    return banned_forever_ids


async def _verify_active_accounts(client: AdminAPIClient) -> tuple[set, set]:
    """
    Verify each locally-active account individually via Admin API.

    This compensates for the Admin API bug where `GET /sessions/?deleted=true`
    doesn't return all deleted sessions. By checking each active account
    one-by-one we catch zombies that the bulk filter misses.

    Returns:
        Tuple of (deleted_ids, frozen_ids) that were found and updated.
    """
    logger.info("🔍 Verifying active accounts individually via Admin API...")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT session_id FROM accounts
            WHERE is_active = 1 AND is_deleted = 0 AND is_frozen = 0
              AND account_type = 'warmup'
        """)
        active_session_ids = [row[0] for row in cursor.fetchall()]

    if not active_session_ids:
        return set(), set()

    verified_deleted = set()
    verified_frozen = set()

    for session_id in active_session_ids:
        try:
            session = await client.get_session_by_id(int(session_id))
        except Exception as e:
            logger.debug(f"Error verifying session {session_id}: {e}")
            continue

        if session is None:
            # Not found in API → treat as deleted
            verified_deleted.add(session_id)
            continue

        if session.get("deleted"):
            verified_deleted.add(session_id)
        if session.get("frozen"):
            verified_frozen.add(session_id)

    # Apply updates
    if verified_deleted:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join(['?' for _ in verified_deleted])
            cursor.execute(
                f"UPDATE accounts SET is_deleted = 1 WHERE session_id IN ({placeholders})",
                list(verified_deleted)
            )
            conn.commit()
        logger.warning(f"🧟 Marked {len(verified_deleted)} zombie-deleted accounts via individual verification")

    if verified_frozen:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join(['?' for _ in verified_frozen])
            cursor.execute(
                f"UPDATE accounts SET is_frozen = 1 WHERE session_id IN ({placeholders})",
                list(verified_frozen)
            )
            conn.commit()
        logger.warning(f"🧟 Marked {len(verified_frozen)} zombie-frozen accounts via individual verification")

    logger.info(
        f"✅ Verification done: {len(active_session_ids)} checked, "
        f"{len(verified_deleted)} deleted, {len(verified_frozen)} frozen"
    )
    return verified_deleted, verified_frozen


# ============================================
# PRE-WARMUP STATUS VERIFICATION (with TTL cache)
# ============================================

# Simple TTL cache: {session_id: (result_dict, timestamp)}
_status_cache: Dict[str, tuple] = {}
_STATUS_CACHE_TTL = 1800  # 30 minutes


async def verify_account_status_via_api(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Verify a single account's status via Admin API before warmup.

    Returns None if the account is OK to proceed.
    Returns a dict with problem details if the account should be skipped:
        {"reason": str, "deleted": bool, "frozen": bool, "status": int}

    Results are cached for 30 minutes to avoid overloading Admin API.
    """
    now = time.time()

    # Check cache
    if session_id in _status_cache:
        cached_result, cached_at = _status_cache[session_id]
        if now - cached_at < _STATUS_CACHE_TTL:
            return cached_result

    client = AdminAPIClient()
    try:
        session = await client.get_session_by_id(int(session_id))
    except Exception as e:
        logger.warning(f"Pre-warmup API check failed for {session_id}: {e}")
        # On error, don't block warmup — return None (OK)
        return None
    finally:
        await client.close()

    if session is None:
        result = {"reason": "session not found in Admin API", "deleted": True, "frozen": False, "status": None}
        _update_local_status(session_id, is_deleted=True)
        _status_cache[session_id] = (result, now)
        return result

    problems = []
    is_deleted = session.get("deleted", False)
    is_frozen = session.get("frozen", False)
    status = session.get("status")

    if is_deleted:
        problems.append("deleted in Admin API")
        _update_local_status(session_id, is_deleted=True)
    if is_frozen:
        problems.append("frozen in Admin API")
        _update_local_status(session_id, is_frozen=True)

    # Hard problems (deleted/frozen) → skip warmup entirely
    if problems:
        result = {
            "reason": "; ".join(problems),
            "deleted": is_deleted,
            "frozen": is_frozen,
            "status": status,
        }
        _status_cache[session_id] = (result, now)
        return result

    # Soft issue: status=1 → passive warmup only (read, view, idle — no messages)
    if status == 1:
        result = {
            "reason": "status=1 (in work, sending broadcasts) — passive warmup only",
            "deleted": False,
            "frozen": False,
            "status": status,
            "passive_only": True,
        }
        _status_cache[session_id] = (result, now)
        return result

    # Account is OK
    _status_cache[session_id] = (None, now)
    return None


def _update_local_status(session_id: str, is_deleted: bool = False, is_frozen: bool = False):
    """Update local DB flags based on Admin API check."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if is_deleted:
                cursor.execute("UPDATE accounts SET is_deleted = 1 WHERE session_id = ?", (session_id,))
            if is_frozen:
                cursor.execute("UPDATE accounts SET is_frozen = 1 WHERE session_id = ?", (session_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"Error updating local status for {session_id}: {e}")


def get_last_sync_time() -> Optional[datetime]:
    """Get the last sync time from a metadata table"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Create metadata table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT
                )
            """)
            conn.commit()
            
            # Get last sync time
            cursor.execute("""
                SELECT value FROM sync_metadata 
                WHERE key = 'last_admin_sync'
            """)
            row = cursor.fetchone()
            
            if row and row[0]:
                return datetime.fromisoformat(row[0])
            
            return None
    except Exception as e:
        logger.error(f"Error getting last sync time: {e}")
        return None


def save_last_sync_time():
    """Save the current time as last sync time"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            now = datetime.utcnow().isoformat()
            cursor.execute("""
                INSERT OR REPLACE INTO sync_metadata (key, value, updated_at)
                VALUES ('last_admin_sync', ?, ?)
            """, (now, now))
            conn.commit()
    except Exception as e:
        logger.error(f"Error saving last sync time: {e}")


async def sync_helper_accounts() -> Dict[str, Any]:
    """
    Sync helper accounts from Admin API to local DB.

    Helper accounts:
    - spamblock=true, status=2, not frozen/deleted
    - account_type='helper', can_initiate_dm=0
    - Can respond to DMs and write in groups

    Returns:
        Dict with sync results
    """
    client = AdminAPIClient()

    try:
        logger.info("🔄 Syncing helper accounts from Admin API...")

        # Fetch helper accounts
        helpers = await client.get_helper_accounts()
        logger.info(f"Found {len(helpers)} helper accounts in Admin API")

        added_count = 0
        updated_count = 0
        skipped_count = 0

        with get_db_connection() as conn:
            cursor = conn.cursor()

            for helper in helpers:
                session_id = str(helper.get('id'))
                phone = helper.get('phone', '')
                first_name = helper.get('first_name', '')
                last_name = helper.get('last_name', '')
                country = helper.get('country', '')
                provider = helper.get('provider', '')

                # Check if account already exists
                cursor.execute(
                    "SELECT id, account_type FROM accounts WHERE session_id = ?",
                    (session_id,)
                )
                existing = cursor.fetchone()

                if existing:
                    # Already exists - update if it's a helper or skip if warmup
                    if existing[1] == 'warmup':
                        # Don't overwrite warmup accounts
                        skipped_count += 1
                        continue
                    else:
                        # Update helper account
                        cursor.execute("""
                            UPDATE accounts SET
                                phone_number = ?,
                                country = ?,
                                provider = ?,
                                is_active = 1,
                                is_frozen = 0,
                                is_deleted = 0,
                                is_banned = 1,
                                can_initiate_dm = 0,
                                account_type = 'helper'
                            WHERE session_id = ?
                        """, (phone, country, provider, session_id))
                        updated_count += 1
                else:
                    # Insert new helper account
                    cursor.execute("""
                        INSERT INTO accounts (
                            session_id, phone_number, country, provider,
                            warmup_stage, is_active, is_frozen, is_deleted,
                            is_banned, can_initiate_dm, account_type,
                            created_at, min_daily_activity, max_daily_activity
                        ) VALUES (?, ?, ?, ?, 14, 1, 0, 0, 1, 0, 'helper', ?, 1, 3)
                    """, (session_id, phone, country, provider, datetime.utcnow().isoformat()))
                    added_count += 1

                    # Generate persona for new helper
                    account_id = cursor.lastrowid
                    _create_helper_persona(cursor, account_id, first_name, last_name)

            conn.commit()

        result = {
            'success': True,
            'total_found': len(helpers),
            'added': added_count,
            'updated': updated_count,
            'skipped': skipped_count,
            'error': None
        }

        logger.info(
            f"✅ Helper sync completed: {added_count} added, "
            f"{updated_count} updated, {skipped_count} skipped (warmup)"
        )

        return result

    except Exception as e:
        logger.error(f"❌ Error syncing helpers: {e}", exc_info=True)
        return {
            'success': False,
            'total_found': 0,
            'added': 0,
            'updated': 0,
            'skipped': 0,
            'error': str(e)
        }
    finally:
        await client.close()


def _create_helper_persona(cursor, account_id: int, first_name: str, last_name: str):
    """Create a basic persona for helper account with behavioral profile"""
    import random
    import json
    from database import generate_behavioral_profile

    # Use real name from Telegram if available, otherwise generate
    if first_name:
        generated_name = f"{first_name} {last_name}".strip()
    else:
        names = [
            "Алексей Петров", "Мария Иванова", "Дмитрий Сидоров",
            "Анна Козлова", "Сергей Новиков", "Елена Морозова",
            "Андрей Волков", "Ольга Соколова", "Николай Лебедев",
            "Татьяна Попова", "Виктор Михайлов", "Наталья Федорова",
            "Павел Кузнецов", "Ирина Захарова", "Максим Орлов",
            "Алена Белова", "Артём Соловьёв", "Юлия Васильева"
        ]
        generated_name = random.choice(names)

    # Expanded interest pool (35+ options)
    all_interests = [
        "технологии", "спорт", "музыка", "кино", "путешествия",
        "книги", "игры", "кулинария", "фотография", "искусство",
        "наука", "финансы", "мода", "автомобили", "здоровье",
        "психология", "дизайн", "архитектура", "история", "политика",
        "природа", "животные", "образование", "бизнес", "маркетинг",
        "программирование", "рукоделие", "садоводство", "рыбалка", "йога",
        "космос", "аниме", "настольные игры", "кроссфит", "кофе",
        "вино", "танцы", "театр"
    ]
    interests = random.sample(all_interests, k=random.randint(2, 5))

    # Expanded communication styles (12 options)
    styles = [
        "дружелюбный", "спокойный", "энергичный", "вдумчивый",
        "ироничный", "лаконичный", "эмоциональный", "серьёзный",
        "оптимистичный", "прагматичный", "любознательный", "сдержанный"
    ]

    # Generate behavioral profile
    persona_data = {"activity_level": random.choice(["low", "moderate", "high"])}
    bp = generate_behavioral_profile(account_id, persona_data)

    cursor.execute("""
        INSERT OR IGNORE INTO personas (
            account_id, generated_name, interests, communication_style,
            behavioral_profile, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        account_id,
        generated_name,
        json.dumps(interests, ensure_ascii=False),
        random.choice(styles),
        json.dumps(bp, ensure_ascii=False),
        datetime.utcnow().isoformat(),
        datetime.utcnow().isoformat()
    ))

