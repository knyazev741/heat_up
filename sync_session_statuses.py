#!/usr/bin/env python3
"""
Sync Session Statuses from Admin API

This script syncs session statuses (frozen, deleted, banned) 
from Admin API to the local heat_up database.
"""

import asyncio
import sys
import logging
from typing import Set
from admin_api_client import AdminAPIClient
from database import get_db_connection

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def sync_frozen_sessions(client: AdminAPIClient) -> Set[str]:
    """
    Sync frozen sessions from Admin API to local DB
    
    Returns:
        Set of frozen session IDs
    """
    logger.info("🔄 Syncing frozen sessions from Admin API...")
    
    # First, reset all frozen flags in local DB
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE accounts SET is_frozen = 0")
        conn.commit()
        logger.info("✅ Reset all is_frozen flags to 0")
    
    # Fetch frozen sessions from Admin API
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
        logger.info(f"  Fetched {len(frozen_ids)} frozen sessions so far...")
    
    # Update local DB
    if frozen_ids:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join(['?' for _ in frozen_ids])
            cursor.execute(
                f"UPDATE accounts SET is_frozen = 1 WHERE session_id IN ({placeholders})",
                list(frozen_ids)
            )
            conn.commit()
            logger.info(f"✅ Marked {len(frozen_ids)} sessions as frozen in local DB")
    
    return frozen_ids


async def sync_deleted_sessions(client: AdminAPIClient) -> Set[str]:
    """
    Sync deleted sessions from Admin API to local DB
    
    Returns:
        Set of deleted session IDs
    """
    logger.info("🔄 Syncing deleted sessions from Admin API...")
    
    # First, reset all deleted flags in local DB
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE accounts SET is_deleted = 0")
        conn.commit()
        logger.info("✅ Reset all is_deleted flags to 0")
    
    # Fetch deleted sessions from Admin API
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
        
        if skip % 1000 == 0:
            logger.info(f"  Fetched {len(deleted_ids)} deleted sessions so far...")
    
    # Update local DB
    if deleted_ids:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Split into chunks of 999 (SQLite limit)
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
            logger.info(f"✅ Marked {len(deleted_ids)} sessions as deleted in local DB")
    
    return deleted_ids


async def sync_banned_forever_sessions(client: AdminAPIClient) -> Set[str]:
    """
    Sync banned forever sessions from Admin API to local DB
    (spamblock=true AND unban_date=null)
    
    Returns:
        Set of banned forever session IDs
    """
    logger.info("🔄 Syncing banned forever sessions from Admin API...")
    
    # First, reset unban_date for all sessions in local DB where is_banned=1
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Set unban_date to a far future date for all currently banned sessions
        # This way we can distinguish between "banned forever" (null) and "temporarily banned" (has date)
        cursor.execute("UPDATE accounts SET unban_date = '2099-01-01' WHERE is_banned = 1")
        conn.commit()
        logger.info("✅ Reset unban_date for all banned sessions")
    
    # Fetch spamblocked sessions from Admin API
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
            # Only include sessions with no unban_date (banned forever)
            if session.get('spamblock') and not session.get('unban_date'):
                session_id = str(session.get('id'))
                banned_forever_ids.add(session_id)
        
        skip += limit
        logger.info(f"  Fetched {len(banned_forever_ids)} banned forever sessions so far...")
    
    # Update local DB - set unban_date to NULL for banned forever sessions
    if banned_forever_ids:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join(['?' for _ in banned_forever_ids])
            cursor.execute(
                f"UPDATE accounts SET is_banned = 1, unban_date = NULL WHERE session_id IN ({placeholders})",
                list(banned_forever_ids)
            )
            conn.commit()
            logger.info(f"✅ Marked {len(banned_forever_ids)} sessions as banned forever in local DB")
    
    return banned_forever_ids


async def main():
    """Main sync function"""
    
    logger.info("=" * 100)
    logger.info("🔄 SYNCING SESSION STATUSES FROM ADMIN API")
    logger.info("=" * 100)
    
    client = AdminAPIClient()
    
    try:
        # Sync frozen sessions
        frozen_ids = await sync_frozen_sessions(client)
        
        # Sync deleted sessions
        deleted_ids = await sync_deleted_sessions(client)
        
        # Sync banned forever sessions
        banned_forever_ids = await sync_banned_forever_sessions(client)
        
        # Summary
        logger.info("\n" + "=" * 100)
        logger.info("📊 SYNC SUMMARY")
        logger.info("=" * 100)
        logger.info(f"🧊 Frozen sessions synced:         {len(frozen_ids)}")
        logger.info(f"❌ Deleted sessions synced:        {len(deleted_ids)}")
        logger.info(f"🚫 Banned forever sessions synced: {len(banned_forever_ids)}")
        logger.info(f"📊 Total problematic sessions:     {len(frozen_ids) + len(deleted_ids) + len(banned_forever_ids)}")
        logger.info("=" * 100)
        
        logger.info("\n✅ Sync completed successfully!")
        
        # Verify the sync
        logger.info("\n🔍 Verifying local DB...")
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM accounts WHERE is_frozen = 1")
            local_frozen = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM accounts WHERE is_deleted = 1")
            local_deleted = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM accounts WHERE is_banned = 1 AND unban_date IS NULL")
            local_banned_forever = cursor.fetchone()[0]
            
            logger.info(f"✅ Local DB frozen count:         {local_frozen}")
            logger.info(f"✅ Local DB deleted count:        {local_deleted}")
            logger.info(f"✅ Local DB banned forever count: {local_banned_forever}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error during sync: {e}", exc_info=True)
        return False
    finally:
        await client.close()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

