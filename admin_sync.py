"""
Admin API Status Sync Module

This module provides functions to sync session statuses from Admin API
that can be imported and used in other modules (like scheduler).
"""

import asyncio
import logging
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
    """Sync frozen sessions"""
    logger.debug("Syncing frozen sessions...")
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE accounts SET is_frozen = 0")
        conn.commit()
    
    result = await client.get_sessions(frozen=True, limit=100)
    total = result.get('total', 0)
    frozen_ids = set()
    
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

