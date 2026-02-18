"""Global safety switch for pausing all warmup actions."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

SWITCH_PATH = Path("data/warmup_actions_switch.json")


def _default_state() -> Dict[str, Any]:
    return {
        "paused": False,
        "reason": "",
        "updated_at": None,
    }


def get_warmup_actions_switch_state() -> Dict[str, Any]:
    """Return current switch state from disk (safe defaults if file missing/broken)."""
    if not SWITCH_PATH.exists():
        return _default_state()

    try:
        data = json.loads(SWITCH_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            logger.warning("Warmup switch file has invalid format, using defaults")
            return _default_state()

        state = _default_state()
        state["paused"] = bool(data.get("paused", False))
        state["reason"] = str(data.get("reason", "") or "")
        state["updated_at"] = data.get("updated_at")
        return state

    except Exception as e:
        logger.error(f"Failed to read warmup switch state: {e}")
        return _default_state()


def is_warmup_actions_paused() -> bool:
    """Quick helper to check whether action execution must be paused."""
    return bool(get_warmup_actions_switch_state().get("paused", False))


def set_warmup_actions_paused(paused: bool, reason: str = "") -> Dict[str, Any]:
    """Persist switch state to disk and return saved state."""
    state = {
        "paused": bool(paused),
        "reason": str(reason or ""),
        "updated_at": datetime.utcnow().isoformat(),
    }

    SWITCH_PATH.parent.mkdir(parents=True, exist_ok=True)
    SWITCH_PATH.write_text(json.dumps(state, ensure_ascii=True, indent=2), encoding="utf-8")

    logger.warning(
        "Warmup actions switch updated: paused=%s, reason=%s",
        state["paused"],
        state["reason"],
    )

    return state
