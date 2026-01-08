"""
Session History Database Management

Manages SQLite database for storing session warmup history.
"""

import sqlite3
import json
import logging
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DATABASE_PATH = "data/sessions.db"


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
                is_deleted BOOLEAN DEFAULT 0,
                unban_date DATETIME,
                llm_generation_disabled BOOLEAN DEFAULT 0,
                
                country TEXT,
                provider TEXT,
                proxy_id INTEGER
            )
        """)
        
        # Migrate existing tables - add new columns if they don't exist
        try:
            cursor.execute("SELECT is_deleted FROM accounts LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Adding is_deleted column to accounts table")
            cursor.execute("ALTER TABLE accounts ADD COLUMN is_deleted BOOLEAN DEFAULT 0")
        
        try:
            cursor.execute("SELECT unban_date FROM accounts LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Adding unban_date column to accounts table")
            cursor.execute("ALTER TABLE accounts ADD COLUMN unban_date DATETIME")
        
        try:
            cursor.execute("SELECT llm_generation_disabled FROM accounts LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Adding llm_generation_disabled column to accounts table")
            cursor.execute("ALTER TABLE accounts ADD COLUMN llm_generation_disabled BOOLEAN DEFAULT 0")
        
        try:
            cursor.execute("SELECT warmup_start_delay_until FROM accounts LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Adding warmup_start_delay_until column to accounts table")
            cursor.execute("ALTER TABLE accounts ADD COLUMN warmup_start_delay_until DATETIME")
        
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

        # ========== PHASE 1: PRIVATE CONVERSATIONS ==========

        # Migration: Add account_type and can_initiate_dm columns to accounts
        try:
            cursor.execute("SELECT account_type FROM accounts LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Adding account_type column to accounts table")
            cursor.execute("ALTER TABLE accounts ADD COLUMN account_type TEXT DEFAULT 'warmup'")

        try:
            cursor.execute("SELECT can_initiate_dm FROM accounts LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Adding can_initiate_dm column to accounts table")
            cursor.execute("ALTER TABLE accounts ADD COLUMN can_initiate_dm BOOLEAN DEFAULT 1")

        # Create private_conversations table for DM dialogs between bots
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS private_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- Participants
                initiator_account_id INTEGER NOT NULL,
                responder_account_id INTEGER NOT NULL,

                -- Telegram session IDs for communication
                initiator_session_id TEXT NOT NULL,
                responder_session_id TEXT NOT NULL,

                -- Context for starting the dialog
                conversation_starter TEXT,
                common_context TEXT,

                -- Topic and state
                current_topic TEXT,
                topics_discussed TEXT,

                -- Timings
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_message_at DATETIME,
                next_response_after DATETIME,

                -- Counters
                message_count INTEGER DEFAULT 0,
                initiator_messages INTEGER DEFAULT 0,
                responder_messages INTEGER DEFAULT 0,

                -- State: active, paused, cooling_down, ended
                status TEXT DEFAULT 'active',
                end_reason TEXT,

                -- Quality score (0-1)
                quality_score REAL,

                FOREIGN KEY (initiator_account_id) REFERENCES accounts(id),
                FOREIGN KEY (responder_account_id) REFERENCES accounts(id)
            )
        """)

        # Create conversation_messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                sender_account_id INTEGER NOT NULL,

                message_text TEXT NOT NULL,
                message_type TEXT DEFAULT 'text',

                sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                telegram_message_id INTEGER,

                -- For tracking if message was delivered/read
                is_delivered BOOLEAN DEFAULT 0,
                is_read BOOLEAN DEFAULT 0,

                FOREIGN KEY (conversation_id) REFERENCES private_conversations(id),
                FOREIGN KEY (sender_account_id) REFERENCES accounts(id)
            )
        """)

        # Indexes for conversations
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversations_initiator
            ON private_conversations(initiator_account_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversations_responder
            ON private_conversations(responder_account_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversations_status
            ON private_conversations(status, next_response_after)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conv_messages
            ON conversation_messages(conversation_id, sent_at)
        """)

        # ============================================
        # BOT GROUPS (Phase 1.3)
        # ============================================

        # Create bot_groups table - private groups between bots
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- Telegram data
                telegram_chat_id INTEGER,
                telegram_invite_link TEXT,
                group_title TEXT NOT NULL,
                group_description TEXT,

                -- Type and topic
                group_type TEXT NOT NULL DEFAULT 'friends',  -- thematic, friends, work
                topic TEXT,

                -- Creator
                creator_account_id INTEGER NOT NULL,
                creator_session_id TEXT NOT NULL,

                -- State
                status TEXT DEFAULT 'active',  -- active, archived
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_activity_at DATETIME,

                -- Counters
                member_count INTEGER DEFAULT 1,
                message_count INTEGER DEFAULT 0,

                -- Scheduling
                next_activity_after DATETIME,

                FOREIGN KEY (creator_account_id) REFERENCES accounts(id)
            )
        """)

        # Create bot_group_members table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_group_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                account_id INTEGER NOT NULL,
                session_id TEXT NOT NULL,

                joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_message_at DATETIME,
                message_count INTEGER DEFAULT 0,

                role TEXT DEFAULT 'member',  -- admin, member

                FOREIGN KEY (group_id) REFERENCES bot_groups(id),
                FOREIGN KEY (account_id) REFERENCES accounts(id),
                UNIQUE(group_id, account_id)
            )
        """)

        # Create bot_group_messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_group_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                sender_account_id INTEGER NOT NULL,

                message_text TEXT,
                message_type TEXT DEFAULT 'text',  -- text, sticker, photo, voice
                reply_to_message_id INTEGER,

                sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                telegram_message_id INTEGER,

                FOREIGN KEY (group_id) REFERENCES bot_groups(id),
                FOREIGN KEY (sender_account_id) REFERENCES accounts(id)
            )
        """)

        # Indexes for bot groups
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_bot_groups_status
            ON bot_groups(status, next_activity_after)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_bot_group_members
            ON bot_group_members(group_id, account_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_bot_group_messages
            ON bot_group_messages(group_id, sent_at)
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
        
    Raises:
        ValueError: If session_id already exists
    """
    try:
        # Check if session_id already exists
        existing = get_account(session_id)
        if existing:
            raise ValueError(
                f"Session ID '{session_id}' already exists in database "
                f"(Account ID: {existing['id']}, Phone: {existing['phone_number']})"
            )
        
        # Генерируем случайную задержку от 0 до 10 часов для новой сессии
        delay_hours = random.uniform(0, 10)
        delay_until = datetime.utcnow() + timedelta(hours=delay_hours)
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO accounts (
                    session_id, phone_number, country, min_daily_activity, max_daily_activity,
                    provider, proxy_id, first_warmup_date, warmup_start_delay_until
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    phone_number,
                    country,
                    min_daily_activity,
                    max_daily_activity,
                    kwargs.get("provider"),
                    kwargs.get("proxy_id"),
                    datetime.utcnow(),
                    delay_until.isoformat()
                )
            )
            conn.commit()
            account_id = cursor.lastrowid
            logger.info(
                f"Added account {session_id} with ID {account_id}. "
                f"Warmup actions will be delayed until {delay_until.isoformat()} "
                f"({delay_hours:.2f} hours delay)"
            )
            return account_id
    except ValueError:
        # Re-raise ValueError with informative message
        raise
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


def should_skip_warmup(account: Dict[str, Any]) -> tuple[bool, str]:
    """
    Проверить, нужно ли пропустить прогрев сессии
    
    Args:
        account: Словарь с данными аккаунта
        
    Returns:
        Кортеж (should_skip: bool, reason: str)
    """
    # Проверка 1: Сессия удалена
    if account.get("is_deleted"):
        return True, "session is deleted"
    
    # Проверка 2: Сессия заморожена
    if account.get("is_frozen"):
        return True, "session is frozen"
    
    # Проверка 3: Бан навсегда (is_banned и нет unban_date)
    # Временные баны (с unban_date) РАЗРЕШЕНЫ - пусть греются
    if account.get("is_banned") and not account.get("unban_date"):
        return True, "session is banned forever (no unban_date)"
    
    # Проверка 4: LLM генерация отключена вручную
    if account.get("llm_generation_disabled"):
        return True, "LLM generation is manually disabled for this session"
    
    # Проверка 5: Сессия неактивна
    if not account.get("is_active"):
        return True, "session is not active"
    
    return False, ""


def get_accounts_for_warmup() -> List[Dict[str, Any]]:
    """
    Get accounts that need warmup right now
    
    Returns:
        List of account dicts that should be warmed up
        (excludes deleted, frozen, banned forever, and manually disabled sessions)
        Note: Temporarily banned sessions (with unban_date) ARE included
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM accounts 
                WHERE is_active = 1 
                  AND is_deleted = 0 
                  AND is_frozen = 0 
                  AND llm_generation_disabled = 0
                  AND (is_banned = 0 OR (is_banned = 1 AND unban_date IS NOT NULL))
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


def get_all_used_names() -> List[str]:
    """
    Get list of all already used persona names
    
    Returns:
        List of used names (e.g. ["Иван Петров", "Мария Смирнова"])
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT generated_name FROM personas WHERE generated_name IS NOT NULL"
            )
            rows = cursor.fetchall()
            return [row[0] for row in rows if row[0]]
    except Exception as e:
        logger.error(f"Error getting used names: {e}")
        return []


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
    Mark chat as joined and increment joined_channels_count in accounts table
    
    Args:
        account_id: Account ID
        chat_username: Chat username
        
    Returns:
        True if successful
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if already joined to avoid double-counting
            cursor.execute(
                "SELECT is_joined FROM discovered_chats WHERE account_id = ? AND chat_username = ?",
                (account_id, chat_username)
            )
            row = cursor.fetchone()
            already_joined = row and row[0] == 1
            
            # Update discovered_chats
            cursor.execute(
                """
                UPDATE discovered_chats 
                SET is_joined = 1, joined_at = ?
                WHERE account_id = ? AND chat_username = ?
                """,
                (datetime.utcnow(), account_id, chat_username)
            )
            
            # Increment joined_channels_count in accounts if this is a new join
            if not already_joined:
                cursor.execute(
                    """
                    UPDATE accounts 
                    SET joined_channels_count = joined_channels_count + 1
                    WHERE id = ?
                    """,
                    (account_id,)
                )
                logger.info(f"Incremented joined_channels_count for account {account_id}")
            
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


def check_warmup_delay(account: Dict[str, Any]) -> tuple[bool, Optional[datetime]]:
    """
    Проверяет, нужно ли ждать перед началом прогрева для новых сессий
    
    Returns:
        (should_wait, delay_until) - нужно ли ждать и до какого времени
    """
    # Если сессия уже прогревалась, задержка не нужна
    if account.get("last_warmup_date"):
        return False, None
    
    delay_until_str = account.get("warmup_start_delay_until")
    if not delay_until_str:
        return False, None
    
    try:
        delay_until = datetime.fromisoformat(delay_until_str)
        now = datetime.utcnow()
        
        if delay_until > now:
            return True, delay_until
        else:
            return False, None
    except Exception as e:
        logger.warning(f"Error checking warmup delay: {e}")
        return False, None


async def wait_for_warmup_delay(account: Dict[str, Any]) -> None:
    """
    Ожидает задержку перед началом прогрева для новых сессий
    
    Используется только в фоновых задачах (scheduler), не в HTTP эндпоинтах!
    
    Для новых сессий (без last_warmup_date) применяется случайная задержка
    от 0 до 10 часов, чтобы избежать одновременного старта множества сессий.
    
    Args:
        account: Данные аккаунта из базы
    """
    import asyncio
    
    should_wait, delay_until = check_warmup_delay(account)
    
    if not should_wait or not delay_until:
        return
    
    now = datetime.utcnow()
    wait_seconds = (delay_until - now).total_seconds()
    wait_hours = wait_seconds / 3600
    
    logger.info(
        f"⏳ Session {account.get('session_id', 'unknown')[:8]}... "
        f"waiting {wait_hours:.2f} hours before starting warmup actions "
        f"(until {delay_until.isoformat()})"
    )
    
    await asyncio.sleep(wait_seconds)
    
    logger.info(
        f"✅ Delay completed for session {account.get('session_id', 'unknown')[:8]}... "
        f"starting warmup actions now"
    )


# ========== PRIVATE CONVERSATIONS CRUD ==========

MIN_STAGE_FOR_DM = 2  # Minimum warmup stage for DM actions


def create_conversation(
    initiator_account_id: int,
    responder_account_id: int,
    initiator_session_id: str,
    responder_session_id: str,
    conversation_starter: str = None,
    common_context: str = None
) -> Optional[int]:
    """
    Create a new private conversation between two accounts

    Args:
        initiator_account_id: Account ID of the initiator
        responder_account_id: Account ID of the responder
        initiator_session_id: Session ID of the initiator
        responder_session_id: Session ID of the responder
        conversation_starter: First message text
        common_context: Context for the conversation

    Returns:
        Conversation ID or None
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO private_conversations (
                    initiator_account_id, responder_account_id,
                    initiator_session_id, responder_session_id,
                    conversation_starter, common_context,
                    started_at, last_message_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    initiator_account_id,
                    responder_account_id,
                    initiator_session_id,
                    responder_session_id,
                    conversation_starter,
                    common_context,
                    datetime.utcnow(),
                    datetime.utcnow()
                )
            )
            conn.commit()
            conversation_id = cursor.lastrowid
            logger.info(f"Created conversation {conversation_id} between {initiator_session_id[:8]} and {responder_session_id[:8]}")
            return conversation_id
    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        return None


def get_conversation(conversation_id: int) -> Optional[Dict[str, Any]]:
    """Get conversation by ID"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM private_conversations WHERE id = ?",
                (conversation_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logger.error(f"Error getting conversation: {e}")
        return None


def get_active_conversation(session_id_1: str, session_id_2: str) -> Optional[Dict[str, Any]]:
    """
    Get active conversation between two sessions

    Args:
        session_id_1: First session ID
        session_id_2: Second session ID

    Returns:
        Conversation dict or None
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM private_conversations
                WHERE status = 'active'
                AND (
                    (initiator_session_id = ? AND responder_session_id = ?)
                    OR
                    (initiator_session_id = ? AND responder_session_id = ?)
                )
                LIMIT 1
                """,
                (session_id_1, session_id_2, session_id_2, session_id_1)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logger.error(f"Error getting active conversation: {e}")
        return None


def get_conversations_needing_response() -> List[Dict[str, Any]]:
    """
    Get conversations where it's time to send a response

    Returns:
        List of conversations that need a response
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Use isoformat() to match the storage format (with T separator)
            cursor.execute(
                """
                SELECT * FROM private_conversations
                WHERE status = 'active'
                AND next_response_after IS NOT NULL
                AND next_response_after <= ?
                ORDER BY next_response_after ASC
                LIMIT 20
                """,
                (datetime.utcnow().isoformat(),)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error getting conversations needing response: {e}")
        return []


def update_conversation(conversation_id: int, **kwargs) -> bool:
    """
    Update conversation fields

    Args:
        conversation_id: Conversation ID
        **kwargs: Fields to update

    Returns:
        True if successful
    """
    if not kwargs:
        return True

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            fields = []
            values = []
            for key, value in kwargs.items():
                fields.append(f"{key} = ?")
                if isinstance(value, datetime):
                    values.append(value.isoformat())
                else:
                    values.append(value)

            values.append(conversation_id)

            query = f"UPDATE private_conversations SET {', '.join(fields)} WHERE id = ?"
            cursor.execute(query, values)
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error updating conversation: {e}")
        return False


def save_conversation_message(
    conversation_id: int,
    sender_account_id: int,
    message_text: str,
    message_type: str = "text",
    telegram_message_id: int = None
) -> Optional[int]:
    """
    Save a message in a conversation

    Args:
        conversation_id: Conversation ID
        sender_account_id: Account ID of the sender
        message_text: Message content
        message_type: Type of message (text, sticker, voice)
        telegram_message_id: Telegram message ID

    Returns:
        Message ID or None
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO conversation_messages (
                    conversation_id, sender_account_id, message_text,
                    message_type, telegram_message_id, sent_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    sender_account_id,
                    message_text,
                    message_type,
                    telegram_message_id,
                    datetime.utcnow()
                )
            )
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Error saving conversation message: {e}")
        return None


def get_conversation_messages(
    conversation_id: int,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Get messages from a conversation

    Args:
        conversation_id: Conversation ID
        limit: Maximum number of messages

    Returns:
        List of message dicts (oldest first)
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT cm.*, a.session_id as sender_session_id, p.generated_name as sender_name
                FROM conversation_messages cm
                JOIN accounts a ON cm.sender_account_id = a.id
                LEFT JOIN personas p ON cm.sender_account_id = p.account_id
                WHERE cm.conversation_id = ?
                ORDER BY cm.sent_at ASC
                LIMIT ?
                """,
                (conversation_id, limit)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error getting conversation messages: {e}")
        return []


def get_last_conversation_message(conversation_id: int) -> Optional[Dict[str, Any]]:
    """Get the last message in a conversation"""
    messages = get_conversation_messages(conversation_id, limit=1)
    # Since we order ASC, we need to get from end
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT cm.*, a.session_id as sender_session_id, p.generated_name as sender_name
                FROM conversation_messages cm
                JOIN accounts a ON cm.sender_account_id = a.id
                LEFT JOIN personas p ON cm.sender_account_id = p.account_id
                WHERE cm.conversation_id = ?
                ORDER BY cm.sent_at DESC
                LIMIT 1
                """,
                (conversation_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logger.error(f"Error getting last conversation message: {e}")
        return None


def get_accounts_eligible_for_dm() -> List[Dict[str, Any]]:
    """
    Get accounts that can participate in DM conversations

    Returns:
        List of accounts with warmup_stage >= MIN_STAGE_FOR_DM
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT a.*, p.generated_name, p.interests, p.communication_style
                FROM accounts a
                LEFT JOIN personas p ON a.id = p.account_id
                WHERE a.is_active = 1
                AND a.is_deleted = 0
                AND a.is_frozen = 0
                AND a.warmup_stage >= ?
                AND (a.is_banned = 0 OR (a.is_banned = 1 AND a.unban_date IS NOT NULL))
                ORDER BY a.warmup_stage DESC, a.last_warmup_date DESC
                """,
                (MIN_STAGE_FOR_DM,)
            )
            rows = cursor.fetchall()
            accounts = []
            for row in rows:
                acc = dict(row)
                if acc.get("interests"):
                    try:
                        acc["interests"] = json.loads(acc["interests"])
                    except:
                        pass
                accounts.append(acc)
            return accounts
    except Exception as e:
        logger.error(f"Error getting accounts eligible for DM: {e}")
        return []


def get_accounts_without_active_conversations(
    min_stage: int = MIN_STAGE_FOR_DM,
    max_active_conversations: int = 2
) -> List[Dict[str, Any]]:
    """
    Get accounts that don't have enough active conversations

    Args:
        min_stage: Minimum warmup stage required
        max_active_conversations: Max number of active conversations

    Returns:
        List of account dicts
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT a.*, p.generated_name, p.interests, p.communication_style,
                    COALESCE(conv_count.active_convs, 0) as active_conversations
                FROM accounts a
                LEFT JOIN personas p ON a.id = p.account_id
                LEFT JOIN (
                    SELECT
                        CASE
                            WHEN initiator_account_id = accounts.id THEN initiator_account_id
                            ELSE responder_account_id
                        END as account_id,
                        COUNT(*) as active_convs
                    FROM private_conversations, accounts
                    WHERE status = 'active'
                    AND (initiator_account_id = accounts.id OR responder_account_id = accounts.id)
                    GROUP BY account_id
                ) conv_count ON a.id = conv_count.account_id
                WHERE a.is_active = 1
                AND a.is_deleted = 0
                AND a.is_frozen = 0
                AND a.warmup_stage >= ?
                AND a.can_initiate_dm = 1
                AND a.account_type = 'warmup'
                AND (a.is_banned = 0 OR (a.is_banned = 1 AND a.unban_date IS NOT NULL))
                AND COALESCE(conv_count.active_convs, 0) < ?
                ORDER BY COALESCE(conv_count.active_convs, 0) ASC, a.warmup_stage DESC
                LIMIT 10
                """,
                (min_stage, max_active_conversations)
            )
            rows = cursor.fetchall()
            accounts = []
            for row in rows:
                acc = dict(row)
                if acc.get("interests"):
                    try:
                        acc["interests"] = json.loads(acc["interests"])
                    except:
                        pass
                accounts.append(acc)
            return accounts
    except Exception as e:
        logger.error(f"Error getting accounts without conversations: {e}")
        return []


def get_potential_conversation_partners(
    initiator_session_id: str,
    limit: int = 10,
    include_helpers: bool = True
) -> List[Dict[str, Any]]:
    """
    Get potential partners for a new conversation.

    Includes both warmup and helper accounts.
    Helpers (spamblock) can respond to DMs but can't initiate.

    Args:
        initiator_session_id: Session ID of the initiator
        limit: Maximum number of partners to return
        include_helpers: Whether to include helper accounts

    Returns:
        List of account dicts with account_type field
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Build account type filter
            if include_helpers:
                # Include both warmup and helper accounts
                # Warmup: not banned OR has unban_date
                # Helper: banned forever but account_type='helper'
                ban_filter = """
                AND (
                    (a.is_banned = 0 OR (a.is_banned = 1 AND a.unban_date IS NOT NULL))
                    OR a.account_type = 'helper'
                )
                """
            else:
                ban_filter = "AND (a.is_banned = 0 OR (a.is_banned = 1 AND a.unban_date IS NOT NULL))"

            cursor.execute(
                f"""
                SELECT a.*, p.generated_name, p.interests, p.communication_style
                FROM accounts a
                LEFT JOIN personas p ON a.id = p.account_id
                WHERE a.session_id != ?
                AND a.is_active = 1
                AND a.is_deleted = 0
                AND a.is_frozen = 0
                {ban_filter}
                AND NOT EXISTS (
                    SELECT 1 FROM private_conversations pc
                    WHERE pc.status = 'active'
                    AND (
                        (pc.initiator_session_id = ? AND pc.responder_session_id = a.session_id)
                        OR (pc.responder_session_id = ? AND pc.initiator_session_id = a.session_id)
                    )
                )
                ORDER BY
                    CASE WHEN a.account_type = 'warmup' THEN 0 ELSE 1 END,
                    a.warmup_stage DESC,
                    RANDOM()
                LIMIT ?
                """,
                (initiator_session_id, initiator_session_id, initiator_session_id, limit)
            )
            rows = cursor.fetchall()
            accounts = []
            for row in rows:
                acc = dict(row)
                if acc.get("interests"):
                    try:
                        acc["interests"] = json.loads(acc["interests"])
                    except:
                        pass
                accounts.append(acc)
            return accounts
    except Exception as e:
        logger.error(f"Error getting potential conversation partners: {e}")
        return []


def count_active_conversations() -> int:
    """Count total active conversations"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM private_conversations WHERE status = 'active'"
            )
            return cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Error counting active conversations: {e}")
        return 0


# ============================================
# BOT GROUPS CRUD (Phase 1.3)
# ============================================

def create_bot_group(
    creator_account_id: int,
    creator_session_id: str,
    group_title: str,
    group_type: str = "friends",
    topic: str = None,
    group_description: str = None,
    telegram_chat_id: int = None,
    telegram_invite_link: str = None
) -> Optional[int]:
    """
    Create a new bot group

    Args:
        creator_account_id: ID of the account creating the group
        creator_session_id: Session ID of the creator
        group_title: Title of the group
        group_type: Type of group (friends, thematic, work)
        topic: Topic of discussion
        group_description: Description of the group
        telegram_chat_id: Telegram chat ID (if already created)
        telegram_invite_link: Invite link for the group

    Returns:
        Group ID if successful, None otherwise
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO bot_groups (
                    creator_account_id, creator_session_id, group_title,
                    group_type, topic, group_description,
                    telegram_chat_id, telegram_invite_link, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    creator_account_id, creator_session_id, group_title,
                    group_type, topic, group_description,
                    telegram_chat_id, telegram_invite_link, datetime.utcnow().isoformat()
                )
            )
            conn.commit()
            group_id = cursor.lastrowid
            logger.info(f"Created bot group {group_id}: {group_title}")
            return group_id
    except Exception as e:
        logger.error(f"Error creating bot group: {e}")
        return None


def get_bot_group(group_id: int) -> Optional[Dict[str, Any]]:
    """Get bot group by ID"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bot_groups WHERE id = ?", (group_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logger.error(f"Error getting bot group: {e}")
        return None


def get_active_bot_groups(limit: int = 50) -> List[Dict[str, Any]]:
    """Get all active bot groups"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM bot_groups
                WHERE status = 'active'
                ORDER BY last_activity_at ASC
                LIMIT ?
                """,
                (limit,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error getting active bot groups: {e}")
        return []


def get_bot_groups_needing_activity() -> List[Dict[str, Any]]:
    """Get bot groups where it's time for activity"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM bot_groups
                WHERE status = 'active'
                AND (next_activity_after IS NULL OR next_activity_after <= ?)
                ORDER BY next_activity_after ASC
                LIMIT 20
                """,
                (datetime.utcnow().isoformat(),)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error getting bot groups needing activity: {e}")
        return []


def update_bot_group(group_id: int, **kwargs) -> bool:
    """Update bot group fields"""
    if not kwargs:
        return True

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            fields = []
            values = []
            for key, value in kwargs.items():
                fields.append(f"{key} = ?")
                if isinstance(value, datetime):
                    values.append(value.isoformat())
                else:
                    values.append(value)

            values.append(group_id)

            query = f"UPDATE bot_groups SET {', '.join(fields)} WHERE id = ?"
            cursor.execute(query, values)
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error updating bot group: {e}")
        return False


def add_group_member(
    group_id: int,
    account_id: int,
    session_id: str,
    role: str = "member"
) -> Optional[int]:
    """Add a member to a bot group"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO bot_group_members
                (group_id, account_id, session_id, role, joined_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (group_id, account_id, session_id, role, datetime.utcnow().isoformat())
            )
            conn.commit()

            # Update member count
            cursor.execute(
                "SELECT COUNT(*) FROM bot_group_members WHERE group_id = ?",
                (group_id,)
            )
            count = cursor.fetchone()[0]
            cursor.execute(
                "UPDATE bot_groups SET member_count = ? WHERE id = ?",
                (count, group_id)
            )
            conn.commit()

            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Error adding group member: {e}")
        return None


def get_group_members(group_id: int) -> List[Dict[str, Any]]:
    """Get all members of a bot group"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT m.*, a.session_id as account_session_id,
                       p.generated_name, p.occupation, p.interests, p.communication_style
                FROM bot_group_members m
                JOIN accounts a ON m.account_id = a.id
                LEFT JOIN personas p ON m.account_id = p.account_id
                WHERE m.group_id = ?
                ORDER BY m.joined_at
                """,
                (group_id,)
            )
            rows = cursor.fetchall()
            members = []
            for row in rows:
                member = dict(row)
                if member.get("interests"):
                    try:
                        member["interests"] = json.loads(member["interests"])
                    except:
                        pass
                members.append(member)
            return members
    except Exception as e:
        logger.error(f"Error getting group members: {e}")
        return []


def update_group_member(group_id: int, account_id: int, **kwargs) -> bool:
    """Update group member fields"""
    if not kwargs:
        return True

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            fields = []
            values = []
            for key, value in kwargs.items():
                fields.append(f"{key} = ?")
                if isinstance(value, datetime):
                    values.append(value.isoformat())
                else:
                    values.append(value)

            values.extend([group_id, account_id])

            query = f"UPDATE bot_group_members SET {', '.join(fields)} WHERE group_id = ? AND account_id = ?"
            cursor.execute(query, values)
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error updating group member: {e}")
        return False


def save_group_message(
    group_id: int,
    sender_account_id: int,
    message_text: str,
    message_type: str = "text",
    telegram_message_id: int = None,
    reply_to_message_id: int = None
) -> Optional[int]:
    """Save a message sent to a bot group"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO bot_group_messages
                (group_id, sender_account_id, message_text, message_type,
                 telegram_message_id, reply_to_message_id, sent_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    group_id, sender_account_id, message_text, message_type,
                    telegram_message_id, reply_to_message_id, datetime.utcnow().isoformat()
                )
            )
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Error saving group message: {e}")
        return None


def get_group_messages(group_id: int, limit: int = 30) -> List[Dict[str, Any]]:
    """Get messages from a bot group"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT m.*, p.generated_name as sender_name
                FROM bot_group_messages m
                LEFT JOIN personas p ON m.sender_account_id = p.account_id
                WHERE m.group_id = ?
                ORDER BY m.sent_at DESC
                LIMIT ?
                """,
                (group_id, limit)
            )
            rows = cursor.fetchall()
            # Reverse to get chronological order
            return [dict(row) for row in reversed(rows)]
    except Exception as e:
        logger.error(f"Error getting group messages: {e}")
        return []


def get_last_group_message(group_id: int) -> Optional[Dict[str, Any]]:
    """Get the last message in a bot group"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT m.*, p.generated_name as sender_name
                FROM bot_group_messages m
                LEFT JOIN personas p ON m.sender_account_id = p.account_id
                WHERE m.group_id = ?
                ORDER BY m.sent_at DESC
                LIMIT 1
                """,
                (group_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logger.error(f"Error getting last group message: {e}")
        return None


def count_active_bot_groups() -> int:
    """Count total active bot groups"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM bot_groups WHERE status = 'active'"
            )
            return cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Error counting active bot groups: {e}")
        return 0


def get_accounts_without_group_membership(
    min_stage: int = MIN_STAGE_FOR_DM,
    limit: int = 20,
    include_helpers: bool = True
) -> List[Dict[str, Any]]:
    """
    Get accounts not currently in any active bot group.

    Includes both warmup and helper accounts.
    Helpers can participate in groups (write messages).

    Args:
        min_stage: Minimum warmup stage (for warmup accounts)
        limit: Max accounts to return
        include_helpers: Whether to include helper accounts

    Returns:
        List of account dicts with account_type field
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Helpers have warmup_stage=14 by default, so stage filter works for both
            # But we also need to allow helpers even if they're "banned"
            if include_helpers:
                account_filter = """
                AND (
                    (a.account_type = 'warmup' AND a.warmup_stage >= ?)
                    OR a.account_type = 'helper'
                )
                """
            else:
                account_filter = "AND a.account_type = 'warmup' AND a.warmup_stage >= ?"

            cursor.execute(
                f"""
                SELECT a.*, p.generated_name, p.interests, p.communication_style
                FROM accounts a
                LEFT JOIN personas p ON a.id = p.account_id
                WHERE a.is_active = 1
                AND a.is_deleted = 0
                AND a.is_frozen = 0
                {account_filter}
                AND NOT EXISTS (
                    SELECT 1 FROM bot_group_members gm
                    JOIN bot_groups g ON gm.group_id = g.id
                    WHERE gm.account_id = a.id
                    AND g.status = 'active'
                )
                ORDER BY
                    CASE WHEN a.account_type = 'warmup' THEN 0 ELSE 1 END,
                    RANDOM()
                LIMIT ?
                """,
                (min_stage, limit)
            )
            rows = cursor.fetchall()
            accounts = []
            for row in rows:
                acc = dict(row)
                if acc.get("interests"):
                    try:
                        acc["interests"] = json.loads(acc["interests"])
                    except:
                        pass
                accounts.append(acc)
            return accounts
    except Exception as e:
        logger.error(f"Error getting accounts without group membership: {e}")
        return []


def count_helper_accounts() -> int:
    """Count active helper accounts in the database"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) FROM accounts
                WHERE account_type = 'helper'
                AND is_active = 1
                AND is_deleted = 0
                AND is_frozen = 0
                """
            )
            return cursor.fetchone()[0]
    except Exception as e:
        logger.error(f"Error counting helper accounts: {e}")
        return 0

