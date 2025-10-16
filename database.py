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
        
        # Create accounts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                phone_number TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                
                warmup_stage INTEGER DEFAULT 1,
                first_warmup_date DATETIME,
                last_warmup_date DATETIME,
                
                min_daily_activity INTEGER DEFAULT 3,
                max_daily_activity INTEGER DEFAULT 6,
                last_activity_times TEXT,
                
                total_warmups INTEGER DEFAULT 0,
                total_actions INTEGER DEFAULT 0,
                joined_channels_count INTEGER DEFAULT 0,
                sent_messages_count INTEGER DEFAULT 0,
                
                is_active BOOLEAN DEFAULT 1,
                is_frozen BOOLEAN DEFAULT 0,
                is_banned BOOLEAN DEFAULT 0,
                
                country TEXT,
                provider TEXT,
                proxy_id INTEGER
            )
        """)
        
        # Create personas table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS personas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                
                generated_name TEXT,
                age INTEGER,
                gender TEXT,
                occupation TEXT,
                city TEXT,
                country TEXT,
                
                personality_traits TEXT,
                interests TEXT,
                communication_style TEXT,
                activity_level TEXT,
                
                full_description TEXT,
                background_story TEXT,
                
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        """)
        
        # Create discovered_chats table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discovered_chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                
                chat_username TEXT NOT NULL,
                chat_title TEXT,
                chat_description TEXT,
                chat_type TEXT,
                member_count INTEGER,
                
                relevance_score FLOAT,
                relevance_reason TEXT,
                
                is_joined BOOLEAN DEFAULT 0,
                joined_at DATETIME,
                is_active BOOLEAN DEFAULT 1,
                last_activity_at DATETIME,
                
                messages_read INTEGER DEFAULT 0,
                messages_sent INTEGER DEFAULT 0,
                reactions_sent INTEGER DEFAULT 0,
                
                discovered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        """)
        
        # Create warmup_sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS warmup_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME,
                
                planned_actions_count INTEGER,
                completed_actions_count INTEGER,
                failed_actions_count INTEGER,
                
                actions_plan TEXT,
                execution_summary TEXT,
                
                warmup_stage INTEGER,
                
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        """)
        
        # Create action_templates table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS action_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                
                action_type TEXT NOT NULL,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                
                last_used_at DATETIME,
                average_duration FLOAT,
                
                used_messages TEXT,
                
                FOREIGN KEY (account_id) REFERENCES accounts(id)
            )
        """)
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_accounts_session 
            ON accounts(session_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_accounts_active 
            ON accounts(is_active, is_banned, is_frozen)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_personas_account 
            ON personas(account_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_discovered_chats_account 
            ON discovered_chats(account_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_warmup_sessions_account 
            ON warmup_sessions(account_id)
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


# ========== ACCOUNTS CRUD ==========

def add_account(
    session_id: str,
    phone_number: str,
    country: Optional[str] = None,
    min_daily_activity: int = 3,
    max_daily_activity: int = 6,
    **kwargs
) -> Optional[int]:
    """
    Add new account to database
    
    Args:
        session_id: Telegram session UID
        phone_number: Phone number
        country: Country code
        min_daily_activity: Minimum warmups per day
        max_daily_activity: Maximum warmups per day
        **kwargs: Additional fields
        
    Returns:
        Account ID or None if failed
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO accounts (
                    session_id, phone_number, country, min_daily_activity, max_daily_activity,
                    provider, proxy_id, first_warmup_date
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    phone_number,
                    country,
                    min_daily_activity,
                    max_daily_activity,
                    kwargs.get("provider"),
                    kwargs.get("proxy_id"),
                    datetime.utcnow()
                )
            )
            conn.commit()
            account_id = cursor.lastrowid
            logger.info(f"Added account {session_id} with ID {account_id}")
            return account_id
    except Exception as e:
        logger.error(f"Error adding account: {e}")
        return None


def get_account(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Get account by session_id
    
    Args:
        session_id: Telegram session UID
        
    Returns:
        Account dict or None
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM accounts WHERE session_id = ?
                """,
                (session_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logger.error(f"Error getting account: {e}")
        return None


def get_account_by_id(account_id: int) -> Optional[Dict[str, Any]]:
    """
    Get account by ID
    
    Args:
        account_id: Account ID
        
    Returns:
        Account dict or None
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM accounts WHERE id = ?
                """,
                (account_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logger.error(f"Error getting account by ID: {e}")
        return None


def update_account_stage(session_id: str, stage: int) -> bool:
    """
    Update warmup stage for account
    
    Args:
        session_id: Telegram session UID
        stage: New warmup stage
        
    Returns:
        True if successful
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE accounts 
                SET warmup_stage = ?, last_warmup_date = ?
                WHERE session_id = ?
                """,
                (stage, datetime.utcnow(), session_id)
            )
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error updating account stage: {e}")
        return False


def update_account(session_id: str, **kwargs) -> bool:
    """
    Update account fields
    
    Args:
        session_id: Telegram session UID
        **kwargs: Fields to update
        
    Returns:
        True if successful
    """
    if not kwargs:
        return True
    
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Build dynamic UPDATE query
            fields = []
            values = []
            for key, value in kwargs.items():
                fields.append(f"{key} = ?")
                values.append(value)
            
            values.append(session_id)
            
            query = f"UPDATE accounts SET {', '.join(fields)} WHERE session_id = ?"
            cursor.execute(query, values)
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error updating account: {e}")
        return False


def get_all_accounts(
    skip: int = 0,
    limit: int = 50,
    active_only: bool = False
) -> List[Dict[str, Any]]:
    """
    Get all accounts with pagination
    
    Args:
        skip: Number of records to skip
        limit: Number of records to return
        active_only: Only return active accounts
        
    Returns:
        List of account dicts
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM accounts"
            if active_only:
                query += " WHERE is_active = 1 AND is_banned = 0 AND is_frozen = 0"
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            
            cursor.execute(query, (limit, skip))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error getting all accounts: {e}")
        return []


def get_accounts_for_warmup() -> List[Dict[str, Any]]:
    """
    Get accounts that need warmup right now
    
    Returns:
        List of account dicts that should be warmed up
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM accounts 
                WHERE is_active = 1 AND is_banned = 0 AND is_frozen = 0
                ORDER BY last_warmup_date ASC NULLS FIRST
                """
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error getting accounts for warmup: {e}")
        return []


# ========== PERSONAS CRUD ==========

def save_persona(account_id: int, persona_data: Dict[str, Any]) -> Optional[int]:
    """
    Save or update persona for account
    
    Args:
        account_id: Account ID
        persona_data: Persona dictionary
        
    Returns:
        Persona ID or None
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if persona exists
            cursor.execute(
                "SELECT id FROM personas WHERE account_id = ?",
                (account_id,)
            )
            existing = cursor.fetchone()
            
            if existing:
                # Update
                cursor.execute(
                    """
                    UPDATE personas SET
                        generated_name = ?,
                        age = ?,
                        gender = ?,
                        occupation = ?,
                        city = ?,
                        country = ?,
                        personality_traits = ?,
                        interests = ?,
                        communication_style = ?,
                        activity_level = ?,
                        full_description = ?,
                        background_story = ?,
                        updated_at = ?
                    WHERE account_id = ?
                    """,
                    (
                        persona_data.get("generated_name"),
                        persona_data.get("age"),
                        persona_data.get("gender"),
                        persona_data.get("occupation"),
                        persona_data.get("city"),
                        persona_data.get("country"),
                        json.dumps(persona_data.get("personality_traits", [])),
                        json.dumps(persona_data.get("interests", [])),
                        persona_data.get("communication_style"),
                        persona_data.get("activity_level"),
                        persona_data.get("full_description"),
                        persona_data.get("background_story"),
                        datetime.utcnow(),
                        account_id
                    )
                )
                persona_id = existing["id"]
            else:
                # Insert
                cursor.execute(
                    """
                    INSERT INTO personas (
                        account_id, generated_name, age, gender, occupation,
                        city, country, personality_traits, interests,
                        communication_style, activity_level,
                        full_description, background_story
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        account_id,
                        persona_data.get("generated_name"),
                        persona_data.get("age"),
                        persona_data.get("gender"),
                        persona_data.get("occupation"),
                        persona_data.get("city"),
                        persona_data.get("country"),
                        json.dumps(persona_data.get("personality_traits", [])),
                        json.dumps(persona_data.get("interests", [])),
                        persona_data.get("communication_style"),
                        persona_data.get("activity_level"),
                        persona_data.get("full_description"),
                        persona_data.get("background_story")
                    )
                )
                persona_id = cursor.lastrowid
            
            conn.commit()
            logger.info(f"Saved persona for account {account_id}")
            return persona_id
    except Exception as e:
        logger.error(f"Error saving persona: {e}")
        return None


def get_persona(account_id: int) -> Optional[Dict[str, Any]]:
    """
    Get persona for account
    
    Args:
        account_id: Account ID
        
    Returns:
        Persona dict or None
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM personas WHERE account_id = ?",
                (account_id,)
            )
            row = cursor.fetchone()
            if row:
                persona = dict(row)
                # Parse JSON fields
                if persona.get("personality_traits"):
                    persona["personality_traits"] = json.loads(persona["personality_traits"])
                if persona.get("interests"):
                    persona["interests"] = json.loads(persona["interests"])
                return persona
            return None
    except Exception as e:
        logger.error(f"Error getting persona: {e}")
        return None


# ========== DISCOVERED CHATS CRUD ==========

def save_discovered_chat(account_id: int, chat_data: Dict[str, Any]) -> Optional[int]:
    """
    Save discovered chat for account
    
    Args:
        account_id: Account ID
        chat_data: Chat dictionary
        
    Returns:
        Chat ID or None
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO discovered_chats (
                    account_id, chat_username, chat_title, chat_description,
                    chat_type, member_count, relevance_score, relevance_reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    account_id,
                    chat_data.get("chat_username"),
                    chat_data.get("chat_title"),
                    chat_data.get("chat_description"),
                    chat_data.get("chat_type"),
                    chat_data.get("member_count"),
                    chat_data.get("relevance_score"),
                    chat_data.get("relevance_reason")
                )
            )
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Error saving discovered chat: {e}")
        return None


def get_relevant_chats(
    account_id: int,
    limit: int = 10,
    joined_only: bool = False
) -> List[Dict[str, Any]]:
    """
    Get relevant chats for account
    
    Args:
        account_id: Account ID
        limit: Max number of chats to return
        joined_only: Only return joined chats
        
    Returns:
        List of chat dicts
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT * FROM discovered_chats 
                WHERE account_id = ? AND is_active = 1
            """
            if joined_only:
                query += " AND is_joined = 1"
            query += " ORDER BY relevance_score DESC, discovered_at DESC LIMIT ?"
            
            cursor.execute(query, (account_id, limit))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error getting relevant chats: {e}")
        return []


def update_chat_joined(account_id: int, chat_username: str) -> bool:
    """
    Mark chat as joined
    
    Args:
        account_id: Account ID
        chat_username: Chat username
        
    Returns:
        True if successful
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE discovered_chats 
                SET is_joined = 1, joined_at = ?
                WHERE account_id = ? AND chat_username = ?
                """,
                (datetime.utcnow(), account_id, chat_username)
            )
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error updating chat joined: {e}")
        return False


# ========== WARMUP SESSIONS CRUD ==========

def save_warmup_session(account_id: int, session_data: Dict[str, Any]) -> Optional[int]:
    """
    Save warmup session
    
    Args:
        account_id: Account ID
        session_data: Session dictionary
        
    Returns:
        Session ID or None
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO warmup_sessions (
                    account_id, planned_actions_count, completed_actions_count,
                    failed_actions_count, actions_plan, execution_summary,
                    warmup_stage, started_at, completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    account_id,
                    session_data.get("planned_actions_count"),
                    session_data.get("completed_actions_count"),
                    session_data.get("failed_actions_count"),
                    json.dumps(session_data.get("actions_plan", [])),
                    json.dumps(session_data.get("execution_summary", {})),
                    session_data.get("warmup_stage"),
                    session_data.get("started_at", datetime.utcnow()),
                    session_data.get("completed_at")
                )
            )
            conn.commit()
            
            # Update account stats
            cursor.execute(
                """
                UPDATE accounts SET 
                    total_warmups = total_warmups + 1,
                    total_actions = total_actions + ?,
                    last_warmup_date = ?
                WHERE id = ?
                """,
                (
                    session_data.get("completed_actions_count", 0),
                    datetime.utcnow(),
                    account_id
                )
            )
            conn.commit()
            
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Error saving warmup session: {e}")
        return None


def get_warmup_sessions(account_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get warmup sessions for account
    
    Args:
        account_id: Account ID
        limit: Max number of sessions
        
    Returns:
        List of session dicts
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM warmup_sessions 
                WHERE account_id = ?
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (account_id, limit)
            )
            rows = cursor.fetchall()
            sessions = []
            for row in rows:
                session = dict(row)
                if session.get("actions_plan"):
                    session["actions_plan"] = json.loads(session["actions_plan"])
                if session.get("execution_summary"):
                    session["execution_summary"] = json.loads(session["execution_summary"])
                sessions.append(session)
            return sessions
    except Exception as e:
        logger.error(f"Error getting warmup sessions: {e}")
        return []

