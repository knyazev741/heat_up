"""
Session History Database Management

Manages SQLite database for storing session warmup history.
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DATABASE_PATH = "sessions.db"


@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    """
    Initialize database and create tables if they don't exist
    """
    logger.info("Initializing session history database...")
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Create session_history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                action_data TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_session_timestamp 
            ON session_history(session_id, timestamp)
        """)
        
        conn.commit()
        
    logger.info("Database initialized successfully")


def save_session_action(
    session_id: str, 
    action_type: str, 
    action_data: Optional[str] = None
):
    """
    Save a session action to database
    
    Args:
        session_id: Telegram session UID
        action_type: Type of action (join_channel, read_messages, idle)
        action_data: JSON string with action details
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO session_history (session_id, action_type, action_data, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, action_type, action_data, datetime.utcnow())
            )
            conn.commit()
            
        logger.debug(f"Saved action {action_type} for session {session_id}")
        
    except Exception as e:
        logger.error(f"Error saving session action: {e}")


def get_session_history(
    session_id: str, 
    days: int = 30
) -> List[Dict[str, Any]]:
    """
    Get session history for the last N days
    
    Args:
        session_id: Telegram session UID
        days: Number of days to look back
        
    Returns:
        List of session actions
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, session_id, action_type, action_data, timestamp
                FROM session_history
                WHERE session_id = ? AND timestamp > ?
                ORDER BY timestamp DESC
                """,
                (session_id, cutoff_date)
            )
            
            rows = cursor.fetchall()
            
            history = []
            for row in rows:
                history.append({
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "action_type": row["action_type"],
                    "action_data": json.loads(row["action_data"]) if row["action_data"] else None,
                    "timestamp": row["timestamp"]
                })
            
            return history
            
    except Exception as e:
        logger.error(f"Error getting session history: {e}")
        return []


def is_new_session(session_id: str, days: int = 30) -> bool:
    """
    Check if this is a new session (no previous warmup history)
    
    Args:
        session_id: Telegram session UID
        days: Number of days to look back
        
    Returns:
        True if session has no previous warmups, False otherwise
    """
    history = get_session_history(session_id, days)
    return len(history) == 0


def get_session_summary(session_id: str, days: int = 30) -> Dict[str, Any]:
    """
    Get a summary of session activity
    
    Args:
        session_id: Telegram session UID
        days: Number of days to look back
        
    Returns:
        Summary with joined channels, activity stats, etc.
    """
    history = get_session_history(session_id, days)
    
    if not history:
        return {
            "is_new": True,
            "total_actions": 0,
            "joined_channels": [],
            "last_activity": None
        }
    
    joined_channels = []
    for action in history:
        if action["action_type"] == "join_channel" and action["action_data"]:
            channel = action["action_data"].get("channel_username")
            if channel and channel not in joined_channels:
                joined_channels.append(channel)
    
    return {
        "is_new": False,
        "total_actions": len(history),
        "joined_channels": joined_channels,
        "last_activity": history[0]["timestamp"] if history else None,
        "recent_actions": history[:5]  # Last 5 actions
    }


def cleanup_old_history(days: int = 30):
    """
    Delete session history older than N days
    
    Args:
        days: Delete records older than this many days
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM session_history WHERE timestamp < ?",
                (cutoff_date,)
            )
            deleted_count = cursor.rowcount
            conn.commit()
            
        logger.info(f"Cleaned up {deleted_count} old session records")
        
    except Exception as e:
        logger.error(f"Error cleaning up old history: {e}")


def get_all_sessions(days: int = 30) -> List[str]:
    """
    Get list of all session IDs with activity in the last N days
    
    Args:
        days: Number of days to look back
        
    Returns:
        List of unique session IDs
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT session_id
                FROM session_history
                WHERE timestamp > ?
                ORDER BY session_id
                """,
                (cutoff_date,)
            )
            
            rows = cursor.fetchall()
            return [row["session_id"] for row in rows]
            
    except Exception as e:
        logger.error(f"Error getting all sessions: {e}")
        return []

