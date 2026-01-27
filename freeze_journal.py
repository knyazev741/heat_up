"""
Freeze Journal Module

Records detailed logs when accounts get frozen, including
action history leading up to the freeze event.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from database import get_db_connection

logger = logging.getLogger(__name__)

# Journal file path
FREEZE_JOURNAL_PATH = "logs/freeze_journal.json"


def ensure_journal_file():
    """Ensure the journal file exists."""
    os.makedirs(os.path.dirname(FREEZE_JOURNAL_PATH), exist_ok=True)
    if not os.path.exists(FREEZE_JOURNAL_PATH):
        with open(FREEZE_JOURNAL_PATH, 'w') as f:
            json.dump([], f)


def get_account_info(session_id: str) -> Optional[Dict[str, Any]]:
    """Get account information from database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                a.id, a.session_id, a.phone_number, a.warmup_stage,
                a.total_warmups, a.first_warmup_date, a.last_warmup_date,
                a.country, a.provider, a.account_type,
                p.generated_name
            FROM accounts a
            LEFT JOIN personas p ON p.account_id = a.id
            WHERE a.session_id = ?
        """, (session_id,))
        row = cursor.fetchone()

        if not row:
            return None

        return {
            "account_id": row[0],
            "session_id": row[1],
            "phone_number": row[2],
            "warmup_stage": row[3],
            "total_warmups": row[4],
            "first_warmup_date": row[5],
            "last_warmup_date": row[6],
            "country": row[7],
            "provider": row[8],
            "account_type": row[9],
            "persona_name": row[10]
        }


def get_action_history(session_id: str, limit: int = 30) -> List[Dict[str, Any]]:
    """Get last N actions for a session."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT action_type, action_data, timestamp
            FROM session_history
            WHERE session_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (session_id, limit))

        actions = []
        for row in cursor.fetchall():
            action_data = None
            if row[1]:
                try:
                    action_data = json.loads(row[1])
                except:
                    action_data = row[1]

            actions.append({
                "action_type": row[0],
                "action_data": action_data,
                "timestamp": row[2]
            })

        return actions


def get_action_stats(session_id: str) -> Dict[str, int]:
    """Get action type statistics for a session."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT action_type, COUNT(*) as cnt
            FROM session_history
            WHERE session_id = ?
            GROUP BY action_type
            ORDER BY cnt DESC
        """, (session_id,))

        return {row[0]: row[1] for row in cursor.fetchall()}


def record_freeze_event(
    session_id: str,
    freeze_source: str = "admin_api_sync",
    admin_api_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Record a freeze event to the journal.

    Args:
        session_id: The frozen session ID
        freeze_source: Where the freeze was detected (admin_api_sync, rpc_error, etc.)
        admin_api_data: Optional data from Admin API about the session

    Returns:
        The recorded journal entry
    """
    ensure_journal_file()

    # Get account info
    account_info = get_account_info(session_id)
    if not account_info:
        logger.warning(f"Could not find account info for session {session_id}")
        account_info = {"session_id": session_id}

    # Get action history
    action_history = get_action_history(session_id, limit=30)

    # Get action stats
    action_stats = get_action_stats(session_id)

    # Create journal entry
    entry = {
        "id": f"{session_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        "session_id": session_id,
        "freeze_detected_at": datetime.utcnow().isoformat(),
        "freeze_source": freeze_source,
        "account_info": account_info,
        "admin_api_data": admin_api_data,
        "action_stats": action_stats,
        "last_actions": action_history,
        "analysis": _analyze_freeze_pattern(account_info, action_history, action_stats)
    }

    # Read existing journal
    try:
        with open(FREEZE_JOURNAL_PATH, 'r') as f:
            journal = json.load(f)
    except:
        journal = []

    # Check if already recorded recently (within last hour)
    recent_threshold = datetime.utcnow().isoformat()[:13]  # Same hour
    for existing in journal:
        if (existing.get("session_id") == session_id and
            existing.get("freeze_detected_at", "")[:13] == recent_threshold):
            logger.debug(f"Freeze for session {session_id} already recorded recently")
            return existing

    # Add new entry
    journal.insert(0, entry)

    # Keep only last 500 entries
    journal = journal[:500]

    # Write back
    with open(FREEZE_JOURNAL_PATH, 'w') as f:
        json.dump(journal, f, indent=2, ensure_ascii=False, default=str)

    logger.info(f"Recorded freeze event for session {session_id}")

    return entry


def _analyze_freeze_pattern(
    account_info: Dict[str, Any],
    action_history: List[Dict[str, Any]],
    action_stats: Dict[str, int]
) -> Dict[str, Any]:
    """Analyze the freeze pattern to identify potential causes."""

    analysis = {
        "account_age_category": "unknown",
        "activity_level": "unknown",
        "suspicious_patterns": [],
        "recommendations": []
    }

    # Account age category
    stage = account_info.get("warmup_stage", 0)
    warmups = account_info.get("total_warmups", 0)

    if stage <= 3 or warmups < 15:
        analysis["account_age_category"] = "young"
        analysis["recommendations"].append("Young accounts are more susceptible to freezing")
    elif stage <= 7 or warmups < 50:
        analysis["account_age_category"] = "medium"
    else:
        analysis["account_age_category"] = "mature"

    # Activity level
    total_actions = sum(action_stats.values())
    if total_actions < 30:
        analysis["activity_level"] = "low"
    elif total_actions < 100:
        analysis["activity_level"] = "medium"
    else:
        analysis["activity_level"] = "high"

    # Suspicious patterns

    # 1. Only idle + view_profile (no real activity)
    real_actions = ["join_channel", "reply_in_chat", "message_bot", "react_to_message", "send_dm"]
    real_action_count = sum(action_stats.get(a, 0) for a in real_actions)
    if real_action_count == 0 and total_actions > 10:
        analysis["suspicious_patterns"].append("no_real_activity")
        analysis["recommendations"].append("Account had no meaningful interactions (only idle/view_profile)")

    # 2. Too many view_profile in a row
    consecutive_view_profile = 0
    max_consecutive = 0
    for action in action_history:
        if action["action_type"] == "view_profile":
            consecutive_view_profile += 1
            max_consecutive = max(max_consecutive, consecutive_view_profile)
        else:
            consecutive_view_profile = 0

    if max_consecutive >= 3:
        analysis["suspicious_patterns"].append("consecutive_view_profile")
        analysis["recommendations"].append(f"Had {max_consecutive} consecutive view_profile actions")

    # 3. High frequency of actions in short time
    if len(action_history) >= 10:
        try:
            first_ts = datetime.fromisoformat(action_history[-1]["timestamp"].replace('T', ' ').split('.')[0])
            last_ts = datetime.fromisoformat(action_history[0]["timestamp"].replace('T', ' ').split('.')[0])
            time_diff = (last_ts - first_ts).total_seconds()
            if time_diff > 0:
                actions_per_hour = len(action_history) / (time_diff / 3600)
                if actions_per_hour > 30:
                    analysis["suspicious_patterns"].append("high_frequency")
                    analysis["recommendations"].append(f"High action frequency: {actions_per_hour:.1f} actions/hour")
        except:
            pass

    # 4. Join channel before other activities
    if action_stats.get("join_channel", 0) > 0 and warmups < 20:
        analysis["suspicious_patterns"].append("early_join_channel")
        analysis["recommendations"].append("Joined channels early in warmup phase")

    return analysis


def get_freeze_journal(
    limit: int = 50,
    offset: int = 0,
    session_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get freeze journal entries.

    Args:
        limit: Maximum entries to return
        offset: Offset for pagination
        session_id: Optional filter by session_id

    Returns:
        List of journal entries
    """
    ensure_journal_file()

    try:
        with open(FREEZE_JOURNAL_PATH, 'r') as f:
            journal = json.load(f)
    except:
        return []

    # Filter by session_id if provided
    if session_id:
        journal = [e for e in journal if e.get("session_id") == session_id]

    # Apply pagination
    return journal[offset:offset + limit]


def get_freeze_journal_count(session_id: Optional[str] = None) -> int:
    """Get total count of freeze journal entries."""
    ensure_journal_file()

    try:
        with open(FREEZE_JOURNAL_PATH, 'r') as f:
            journal = json.load(f)
    except:
        return 0

    if session_id:
        return len([e for e in journal if e.get("session_id") == session_id])

    return len(journal)


def record_existing_frozen_accounts():
    """
    Record journal entries for all currently frozen accounts.
    Useful for backfilling historical data.
    """
    logger.info("Recording journal entries for existing frozen accounts...")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT session_id FROM accounts
            WHERE is_frozen = 1 AND is_deleted = 0 AND total_warmups > 0
        """)

        frozen_sessions = [row[0] for row in cursor.fetchall()]

    recorded = 0
    for session_id in frozen_sessions:
        entry = record_freeze_event(
            session_id,
            freeze_source="historical_backfill"
        )
        if entry:
            recorded += 1

    logger.info(f"Recorded {recorded} historical freeze events")
    return recorded
