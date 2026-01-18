"""
Data formatting utilities for dashboard.
"""

from datetime import datetime, timedelta
from typing import Optional


def relative_time(timestamp: Optional[str]) -> str:
    """Convert timestamp to relative time string (e.g., '2 часа назад')."""
    if not timestamp:
        return "Никогда"

    try:
        if isinstance(timestamp, str):
            # Try different formats
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
                try:
                    dt = datetime.strptime(timestamp.split(".")[0], fmt)
                    break
                except ValueError:
                    continue
            else:
                return timestamp
        else:
            dt = timestamp

        now = datetime.now()
        diff = now - dt

        if diff.days > 365:
            years = diff.days // 365
            return f"{years} {'год' if years == 1 else 'года' if 2 <= years <= 4 else 'лет'} назад"
        elif diff.days > 30:
            months = diff.days // 30
            return f"{months} {'месяц' if months == 1 else 'месяца' if 2 <= months <= 4 else 'месяцев'} назад"
        elif diff.days > 0:
            return f"{diff.days} {'день' if diff.days == 1 else 'дня' if 2 <= diff.days <= 4 else 'дней'} назад"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} {'час' if hours == 1 else 'часа' if 2 <= hours <= 4 else 'часов'} назад"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} {'минуту' if minutes == 1 else 'минуты' if 2 <= minutes <= 4 else 'минут'} назад"
        else:
            return "Только что"

    except Exception:
        return str(timestamp)


def mask_phone(phone: Optional[str]) -> str:
    """Mask phone number for privacy (e.g., +7***1234)."""
    if not phone:
        return "—"

    phone = str(phone)
    if len(phone) < 6:
        return phone

    # Keep first 2-3 chars and last 4 chars
    if phone.startswith("+"):
        prefix = phone[:3]  # +7 or +38
        suffix = phone[-4:]
        return f"{prefix}***{suffix}"
    else:
        return f"{phone[:2]}***{phone[-4:]}"


def stage_color(stage: int) -> str:
    """Get color for warmup stage."""
    if stage is None:
        return "gray"
    elif stage <= 3:
        return "green"
    elif stage <= 6:
        return "yellow"
    elif stage <= 9:
        return "blue"
    else:
        return "purple"


def stage_badge_class(stage: int) -> str:
    """Get Tailwind classes for stage badge."""
    color = stage_color(stage)
    color_map = {
        "green": "bg-green-600 text-white",
        "yellow": "bg-yellow-500 text-black",
        "blue": "bg-blue-600 text-white",
        "purple": "bg-purple-600 text-white",
        "gray": "bg-gray-500 text-white"
    }
    return color_map.get(color, "bg-gray-500 text-white")


def status_badge(is_active: bool, is_frozen: bool, is_banned: bool) -> tuple[str, str]:
    """Get status text and color."""
    if is_banned:
        return "Забанен", "red"
    elif is_frozen:
        return "Заморожен", "orange"
    elif is_active:
        return "Активен", "green"
    else:
        return "Неактивен", "gray"


def format_number(num: Optional[int]) -> str:
    """Format large numbers with K/M suffix."""
    if num is None:
        return "0"

    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    else:
        return str(num)


def truncate(text: Optional[str], max_length: int = 50) -> str:
    """Truncate text with ellipsis."""
    if not text:
        return ""

    text = str(text)
    if len(text) <= max_length:
        return text

    return text[:max_length - 3] + "..."


def action_type_label(action_type: str) -> str:
    """Get human-readable label for action type (English)."""
    labels = {
        "warmup_session": "Warmup Session",
        "join_channel": "Join Channel",
        "send_message": "Send Message",
        "reply_to_dm": "Reply to DM",
        "reply_in_chat": "Reply in Chat",
        "send_reaction": "Send Reaction",
        "read_channel": "Read Channel",
        "search_channels": "Search Channels",
        "profile_update": "Profile Update",
        "view_sponsored_ad": "View Sponsored Ad",
        "message_bot": "Message Bot",
        "react_to_message": "React to Message",
        "forward_message": "Forward Message",
        "view_profile": "View Profile",
        "idle": "Idle",
        "sync_contacts": "Sync Contacts",
        "update_privacy": "Update Privacy",
        "create_group": "Create Group",
        "error": "Error"
    }
    return labels.get(action_type, action_type)


def action_type_color(action_type: str) -> str:
    """Get color for action type."""
    colors = {
        "warmup_session": "blue",
        "join_channel": "green",
        "send_message": "cyan",
        "reply_to_dm": "purple",
        "reply_in_chat": "indigo",
        "send_reaction": "yellow",
        "read_channel": "gray",
        "search_channels": "teal",
        "profile_update": "orange",
        "view_sponsored_ad": "pink",
        "error": "red"
    }
    return colors.get(action_type, "gray")
