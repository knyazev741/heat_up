"""
SQL queries for dashboard data retrieval.
All queries use the main database at data/sessions.db
"""

import sqlite3
import json
import os
import httpx
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path

DATABASE_PATH = Path(__file__).parent.parent.parent / "data" / "sessions.db"

def get_db_connection():
    """Get database connection with row factory."""
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ==================== KPI Stats ====================

def get_kpi_stats() -> Dict[str, int]:
    """Get main KPI statistics."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Total accounts (not deleted)
    cursor.execute("SELECT COUNT(*) FROM accounts WHERE is_deleted = 0")
    total = cursor.fetchone()[0]

    # Active warmup accounts
    cursor.execute("""
        SELECT COUNT(*) FROM accounts
        WHERE is_deleted = 0
        AND is_active = 1
        AND is_banned = 0
        AND is_frozen = 0
        AND account_type = 'warmup'
    """)
    active_warmup = cursor.fetchone()[0]

    # Helper accounts
    cursor.execute("""
        SELECT COUNT(*) FROM accounts
        WHERE is_deleted = 0
        AND is_active = 1
        AND account_type = 'helper'
    """)
    helpers = cursor.fetchone()[0]

    # Total actions today
    cursor.execute("""
        SELECT COUNT(*) FROM session_history
        WHERE date(timestamp) = date('now')
    """)
    actions_today = cursor.fetchone()[0]

    conn.close()

    return {
        "total_accounts": total,
        "active_warmup": active_warmup,
        "helpers": helpers,
        "actions_today": actions_today
    }


def get_ready_accounts_count() -> int:
    """
    Get count of 'ready' accounts.
    Ready = warmup_stage >= 5, is_premium=0, status=0 in Admin API.

    First queries local DB for accounts with stage >= 5,
    then verifies they are ready in Admin API.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get warmup accounts with stage >= 5 that are active
    cursor.execute("""
        SELECT session_id FROM accounts
        WHERE is_deleted = 0
        AND is_active = 1
        AND is_banned = 0
        AND is_frozen = 0
        AND account_type = 'warmup'
        AND warmup_stage >= 5
    """)

    local_ready_sessions = {row[0] for row in cursor.fetchall()}
    conn.close()

    if not local_ready_sessions:
        return 0

    try:
        # Load Admin API config
        api_config_path = Path(__file__).parent.parent.parent / "data" / "adminapi.json"
        if not api_config_path.exists():
            return len(local_ready_sessions)  # Return local count if no API config

        with open(api_config_path) as f:
            config = json.load(f)

        base_url = config.get("base_url", "")
        api_key = config.get("api_key", "")

        if not base_url or not api_key:
            return len(local_ready_sessions)

        # Call Admin API for accounts with status=0, is_premium=false
        headers = {"Authorization": f"Token {api_key}"}
        response = httpx.get(
            f"{base_url}/api/v1/sessions/",
            params={"status": 0, "is_premium": "false", "deleted": "false"},
            headers=headers,
            timeout=10.0
        )

        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict) and "results" in data:
                api_sessions = {s.get("session_id") or s.get("id") for s in data["results"]}
            elif isinstance(data, list):
                api_sessions = {s.get("session_id") or s.get("id") for s in data}
            else:
                return len(local_ready_sessions)

            # Count accounts that are both in local ready set AND in API with correct status
            ready_count = len(local_ready_sessions & api_sessions)
            return ready_count if ready_count > 0 else len(local_ready_sessions)

        return len(local_ready_sessions)
    except Exception:
        return len(local_ready_sessions)


def get_stage_distribution() -> List[Dict[str, Any]]:
    """Get distribution of accounts by warmup stage."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            warmup_stage,
            COUNT(*) as count
        FROM accounts
        WHERE is_deleted = 0 AND account_type = 'warmup'
        GROUP BY warmup_stage
        ORDER BY warmup_stage
    """)

    result = [{"stage": row[0], "count": row[1]} for row in cursor.fetchall()]
    conn.close()
    return result


def get_country_distribution() -> List[Dict[str, Any]]:
    """Get distribution of warmup accounts by country (only active warmup)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COALESCE(country, 'Unknown') as country,
            COUNT(*) as count
        FROM accounts
        WHERE is_deleted = 0
        AND account_type = 'warmup'
        GROUP BY country
        ORDER BY count DESC
    """)

    result = [{"country": row[0], "count": row[1]} for row in cursor.fetchall()]
    conn.close()
    return result


def get_activity_by_day(days: int = 14) -> List[Dict[str, Any]]:
    """Get activity (actions) by day for the last N days."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            date(timestamp) as day,
            COUNT(*) as count
        FROM session_history
        WHERE timestamp >= datetime('now', ?)
        GROUP BY date(timestamp)
        ORDER BY day
    """, (f"-{days} days",))

    result = [{"day": row[0], "count": row[1]} for row in cursor.fetchall()]
    conn.close()
    return result


def get_recent_accounts(limit: int = 5) -> List[Dict[str, Any]]:
    """Get most recently created accounts."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            a.id,
            a.session_id,
            a.phone_number,
            a.warmup_stage,
            a.account_type,
            a.created_at,
            a.is_active,
            a.is_frozen,
            a.is_banned,
            p.generated_name
        FROM accounts a
        LEFT JOIN personas p ON a.id = p.account_id
        WHERE a.is_deleted = 0
        ORDER BY a.created_at DESC
        LIMIT ?
    """, (limit,))

    result = []
    for row in cursor.fetchall():
        result.append({
            "id": row[0],
            "session_id": row[1],
            "phone": row[2],
            "stage": row[3],
            "type": row[4],
            "created_at": row[5],
            "is_active": row[6],
            "is_frozen": row[7],
            "is_banned": row[8],
            "persona_name": row[9]
        })

    conn.close()
    return result


def get_recent_actions(limit: int = 10) -> List[Dict[str, Any]]:
    """Get most recent actions from session_history."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            sh.id,
            sh.session_id,
            sh.action_type,
            sh.action_data,
            sh.timestamp,
            a.id as account_id,
            p.generated_name
        FROM session_history sh
        LEFT JOIN accounts a ON sh.session_id = a.session_id
        LEFT JOIN personas p ON a.id = p.account_id
        ORDER BY sh.timestamp DESC
        LIMIT ?
    """, (limit,))

    result = []
    for row in cursor.fetchall():
        action_data = {}
        if row[3]:
            try:
                action_data = json.loads(row[3])
            except json.JSONDecodeError:
                pass

        result.append({
            "id": row[0],
            "session_id": row[1],
            "action_type": row[2],
            "action_data": action_data,
            "timestamp": row[4],
            "account_id": row[5],
            "persona_name": row[6]
        })

    conn.close()
    return result


# ==================== Accounts ====================

def get_accounts(
    search: str = "",
    account_type: str = "all",
    stages: List[int] = None,
    status: str = "all",
    country: str = "",
    limit: int = 25,
    offset: int = 0
) -> tuple[List[Dict], int]:
    """Get accounts list with filters and pagination."""
    conn = get_db_connection()
    cursor = conn.cursor()

    conditions = ["a.is_deleted = 0"]
    params = []

    # Search filter
    if search:
        conditions.append("""
            (a.session_id LIKE ? OR a.phone_number LIKE ? OR p.generated_name LIKE ?)
        """)
        search_pattern = f"%{search}%"
        params.extend([search_pattern, search_pattern, search_pattern])

    # Type filter
    if account_type != "all":
        conditions.append("a.account_type = ?")
        params.append(account_type)

    # Stage filter
    if stages:
        placeholders = ",".join("?" * len(stages))
        conditions.append(f"a.warmup_stage IN ({placeholders})")
        params.extend(stages)

    # Status filter
    if status == "active":
        conditions.append("a.is_active = 1 AND a.is_frozen = 0 AND a.is_banned = 0")
    elif status == "frozen":
        conditions.append("a.is_frozen = 1")
    elif status == "banned":
        conditions.append("a.is_banned = 1")

    # Country filter
    if country:
        conditions.append("a.country = ?")
        params.append(country)

    where_clause = " AND ".join(conditions)

    # Get total count
    count_query = f"""
        SELECT COUNT(*) FROM accounts a
        LEFT JOIN personas p ON a.id = p.account_id
        WHERE {where_clause}
    """
    cursor.execute(count_query, params)
    total = cursor.fetchone()[0]

    # Get accounts
    query = f"""
        SELECT
            a.id,
            a.session_id,
            a.phone_number,
            a.warmup_stage,
            a.account_type,
            a.country,
            a.is_active,
            a.is_frozen,
            a.is_banned,
            a.total_actions,
            a.last_warmup_date,
            a.created_at,
            p.generated_name
        FROM accounts a
        LEFT JOIN personas p ON a.id = p.account_id
        WHERE {where_clause}
        ORDER BY a.created_at DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    cursor.execute(query, params)

    result = []
    for row in cursor.fetchall():
        result.append({
            "id": row[0],
            "session_id": row[1],
            "phone": row[2],
            "stage": row[3],
            "type": row[4],
            "country": row[5],
            "is_active": row[6],
            "is_frozen": row[7],
            "is_banned": row[8],
            "total_actions": row[9],
            "last_activity": row[10],
            "created_at": row[11],
            "persona_name": row[12]
        })

    conn.close()
    return result, total


def get_account_details(account_id: int) -> Optional[Dict[str, Any]]:
    """Get detailed information about an account."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get account
    cursor.execute("""
        SELECT
            a.*,
            p.id as persona_id,
            p.generated_name,
            p.age,
            p.gender,
            p.occupation,
            p.city,
            p.country as persona_country,
            p.personality_traits,
            p.interests,
            p.communication_style,
            p.activity_level,
            p.full_description,
            p.background_story
        FROM accounts a
        LEFT JOIN personas p ON a.id = p.account_id
        WHERE a.id = ?
    """, (account_id,))

    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    # Convert Row to dict
    account = dict(row)

    # Get conversations count
    cursor.execute("""
        SELECT COUNT(*) FROM private_conversations
        WHERE initiator_account_id = ? OR responder_account_id = ?
    """, (account_id, account_id))
    account["conversations_count"] = cursor.fetchone()[0]

    # Get joined channels count
    cursor.execute("""
        SELECT COUNT(*) FROM discovered_chats
        WHERE account_id = ? AND is_joined = 1
    """, (account_id,))
    account["joined_channels_count"] = cursor.fetchone()[0]

    conn.close()
    return account


def get_account_connections(account_id: int) -> List[Dict[str, Any]]:
    """Get DM connections for an account."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            pc.id,
            CASE
                WHEN pc.initiator_account_id = ? THEN pc.responder_account_id
                ELSE pc.initiator_account_id
            END as partner_account_id,
            CASE
                WHEN pc.initiator_account_id = ? THEN pc.responder_session_id
                ELSE pc.initiator_session_id
            END as partner_session_id,
            pc.message_count,
            pc.last_message_at,
            pc.status,
            CASE WHEN pc.initiator_account_id = ? THEN 'initiated' ELSE 'received' END as direction,
            p.generated_name as partner_name
        FROM private_conversations pc
        LEFT JOIN accounts a ON (
            CASE
                WHEN pc.initiator_account_id = ? THEN pc.responder_account_id
                ELSE pc.initiator_account_id
            END = a.id
        )
        LEFT JOIN personas p ON a.id = p.account_id
        WHERE pc.initiator_account_id = ? OR pc.responder_account_id = ?
        ORDER BY pc.last_message_at DESC
    """, (account_id, account_id, account_id, account_id, account_id, account_id))

    result = []
    for row in cursor.fetchall():
        result.append({
            "id": row[0],
            "partner_account_id": row[1],
            "partner_session_id": row[2],
            "message_count": row[3],
            "last_message_at": row[4],
            "status": row[5],
            "direction": row[6],
            "partner_name": row[7]
        })

    conn.close()
    return result


def get_account_chats(account_id: int) -> List[Dict[str, Any]]:
    """Get discovered/joined chats for an account."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id, chat_username, chat_title, chat_type, member_count,
            is_joined, joined_at, messages_sent, reactions_sent,
            relevance_score
        FROM discovered_chats
        WHERE account_id = ?
        ORDER BY is_joined DESC, relevance_score DESC
    """, (account_id,))

    result = []
    for row in cursor.fetchall():
        result.append({
            "id": row[0],
            "username": row[1],
            "title": row[2],
            "type": row[3],
            "members": row[4],
            "is_joined": row[5],
            "joined_at": row[6],
            "messages_sent": row[7],
            "reactions_sent": row[8],
            "relevance": row[9]
        })

    conn.close()
    return result


def get_account_history(account_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """Get action history for an account."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get session_id first
    cursor.execute("SELECT session_id FROM accounts WHERE id = ?", (account_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return []

    session_id = row[0]

    cursor.execute("""
        SELECT id, action_type, action_data, timestamp
        FROM session_history
        WHERE session_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
    """, (session_id, limit))

    result = []
    for row in cursor.fetchall():
        action_data = {}
        if row[2]:
            try:
                action_data = json.loads(row[2])
            except json.JSONDecodeError:
                pass

        result.append({
            "id": row[0],
            "action_type": row[1],
            "action_data": action_data,
            "timestamp": row[3]
        })

    conn.close()
    return result


def get_countries() -> List[str]:
    """Get list of unique countries from accounts."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT country FROM accounts
        WHERE country IS NOT NULL AND country != ''
        ORDER BY country
    """)

    result = [row[0] for row in cursor.fetchall()]
    conn.close()
    return result


# ==================== Connections Graph ====================

def get_graph_nodes() -> List[Dict[str, Any]]:
    """Get all nodes (accounts) for the connections graph."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            a.id, a.session_id, a.warmup_stage, a.account_type,
            p.generated_name,
            (SELECT COUNT(*) FROM session_history WHERE session_id = a.session_id) as total_actions
        FROM accounts a
        LEFT JOIN personas p ON a.id = p.account_id
        WHERE a.is_deleted = 0
    """)

    result = []
    for row in cursor.fetchall():
        result.append({
            "id": row[0],
            "session_id": row[1],
            "stage": row[2],
            "type": row[3],
            "name": row[4] or f"Account {row[0]}",
            "actions": row[5]
        })

    conn.close()
    return result


def get_graph_edges() -> List[Dict[str, Any]]:
    """Get all edges (connections) for the graph."""
    conn = get_db_connection()
    cursor = conn.cursor()

    edges = []

    # DM connections
    cursor.execute("""
        SELECT
            initiator_account_id, responder_account_id, message_count
        FROM private_conversations
        WHERE status != 'ended' OR message_count > 0
    """)

    for row in cursor.fetchall():
        edges.append({
            "from": row[0],
            "to": row[1],
            "weight": row[2] or 1,
            "type": "dm"
        })

    # Group connections
    cursor.execute("""
        SELECT DISTINCT bgm1.account_id, bgm2.account_id, bgm1.group_id
        FROM bot_group_members bgm1
        JOIN bot_group_members bgm2 ON bgm1.group_id = bgm2.group_id
        WHERE bgm1.account_id < bgm2.account_id
    """)

    for row in cursor.fetchall():
        edges.append({
            "from": row[0],
            "to": row[1],
            "weight": 1,
            "type": "group",
            "group_id": row[2]
        })

    conn.close()
    return edges


# ==================== Channels ====================

def get_discovered_chats_aggregated() -> List[Dict[str, Any]]:
    """Get aggregated discovered chats."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            chat_username,
            chat_title,
            chat_type,
            MAX(member_count) as member_count,
            COUNT(*) as accounts_discovered,
            SUM(CASE WHEN is_joined = 1 THEN 1 ELSE 0 END) as accounts_joined,
            AVG(relevance_score) as avg_relevance
        FROM discovered_chats
        GROUP BY chat_username
        ORDER BY accounts_joined DESC, accounts_discovered DESC
    """)

    result = []
    for row in cursor.fetchall():
        result.append({
            "username": row[0],
            "title": row[1],
            "type": row[2],
            "members": row[3],
            "discovered_by": row[4],
            "joined_by": row[5],
            "relevance": round(row[6], 2) if row[6] else None
        })

    conn.close()
    return result


def get_bot_groups() -> List[Dict[str, Any]]:
    """Get bot groups with stats."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            bg.id, bg.group_title, bg.group_type, bg.topic,
            bg.member_count, bg.message_count, bg.status,
            bg.created_at, bg.last_activity_at
        FROM bot_groups bg
        ORDER BY bg.last_activity_at DESC
    """)

    result = []
    for row in cursor.fetchall():
        result.append({
            "id": row[0],
            "title": row[1],
            "type": row[2],
            "topic": row[3],
            "members": row[4],
            "messages": row[5],
            "status": row[6],
            "created_at": row[7],
            "last_activity": row[8]
        })

    conn.close()
    return result


def get_real_chat_participation_aggregated() -> List[Dict[str, Any]]:
    """Get aggregated real chat participation stats."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            chat_username,
            COUNT(DISTINCT account_id) as accounts_count,
            SUM(messages_sent) as total_messages,
            SUM(reactions_sent) as total_reactions,
            MAX(last_message_at) as last_activity
        FROM real_chat_participation
        GROUP BY chat_username
        ORDER BY total_messages DESC
    """)

    result = []
    for row in cursor.fetchall():
        result.append({
            "username": row[0],
            "accounts": row[1],
            "messages": row[2],
            "reactions": row[3],
            "last_activity": row[4]
        })

    conn.close()
    return result


# ==================== Logs ====================

def get_global_logs(
    start_date: str = None,
    end_date: str = None,
    action_types: List[str] = None,
    account_id: int = None,
    search: str = "",
    limit: int = 100,
    offset: int = 0
) -> tuple[List[Dict], int]:
    """Get global logs with filters."""
    conn = get_db_connection()
    cursor = conn.cursor()

    conditions = ["1=1"]
    params = []

    if start_date:
        conditions.append("sh.timestamp >= ?")
        params.append(start_date)

    if end_date:
        conditions.append("sh.timestamp <= ?")
        params.append(end_date + " 23:59:59")

    if action_types:
        placeholders = ",".join("?" * len(action_types))
        conditions.append(f"sh.action_type IN ({placeholders})")
        params.extend(action_types)

    if account_id:
        conditions.append("a.id = ?")
        params.append(account_id)

    if search:
        conditions.append("(sh.action_data LIKE ? OR sh.action_type LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    where_clause = " AND ".join(conditions)

    # Get total count
    count_query = f"""
        SELECT COUNT(*) FROM session_history sh
        LEFT JOIN accounts a ON sh.session_id = a.session_id
        WHERE {where_clause}
    """
    cursor.execute(count_query, params)
    total = cursor.fetchone()[0]

    # Get logs
    query = f"""
        SELECT
            sh.id, sh.session_id, sh.action_type, sh.action_data, sh.timestamp,
            a.id as account_id, p.generated_name
        FROM session_history sh
        LEFT JOIN accounts a ON sh.session_id = a.session_id
        LEFT JOIN personas p ON a.id = p.account_id
        WHERE {where_clause}
        ORDER BY sh.timestamp DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    cursor.execute(query, params)

    result = []
    for row in cursor.fetchall():
        action_data = {}
        if row[3]:
            try:
                action_data = json.loads(row[3])
            except json.JSONDecodeError:
                pass

        result.append({
            "id": row[0],
            "session_id": row[1],
            "action_type": row[2],
            "action_data": action_data,
            "timestamp": row[4],
            "account_id": row[5],
            "persona_name": row[6]
        })

    conn.close()
    return result, total


def get_action_types() -> List[str]:
    """Get list of unique action types."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT action_type FROM session_history
        ORDER BY action_type
    """)

    result = [row[0] for row in cursor.fetchall()]
    conn.close()
    return result


# ==================== Settings ====================

def get_scheduler_status() -> Dict[str, Any]:
    """Get scheduler status from main API."""
    try:
        response = httpx.get("http://localhost:8080/scheduler/status", timeout=5.0)
        if response.status_code == 200:
            data = response.json()
            # Map API response to dashboard format
            return {
                "running": data.get("is_running", False),
                "next_check": f"{data.get('next_check_in', 0) // 60} мин" if data.get("next_check_in") else None,
                "active_warmups": data.get("accounts_scheduled", 0),
                "helper_accounts": data.get("helper_accounts", 0),
                "active_conversations": data.get("active_conversations", 0),
                "active_groups": data.get("active_groups", 0),
            }
    except Exception as e:
        pass
    return {"running": False, "error": "Unable to connect"}


def cleanup_old_logs(days: int) -> int:
    """Delete logs older than N days. Returns count of deleted rows."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM session_history
        WHERE timestamp < datetime('now', ?)
    """, (f"-{days} days",))

    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted
