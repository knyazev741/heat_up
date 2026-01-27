"""
Freeze Journal page - view frozen accounts and their action history.
"""

from nicegui import ui
from datetime import datetime
import json

from dashboard.auth import is_authenticated
from dashboard.components.layout import page_layout, card, badge
from dashboard.utils.formatters import relative_time

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from freeze_journal import get_freeze_journal, get_freeze_journal_count


def action_type_color(action_type: str) -> str:
    """Get color for action type."""
    colors = {
        "idle": "grey",
        "view_profile": "blue",
        "read_messages": "cyan",
        "join_channel": "green",
        "reply_in_chat": "purple",
        "react_to_message": "orange",
        "message_bot": "teal",
        "send_dm": "pink",
        "update_profile": "amber"
    }
    return colors.get(action_type, "grey")


def create_freeze_journal_page():
    """Create the freeze journal page."""

    # State
    state = {
        "page": 0,
        "page_size": 20,
        "entries": [],
        "total": 0,
        "selected_entry": None
    }

    entries_container = None
    detail_container = None
    pagination_container = None

    def load_entries():
        """Load journal entries."""
        state["entries"] = get_freeze_journal(
            limit=state["page_size"],
            offset=state["page"] * state["page_size"]
        )
        state["total"] = get_freeze_journal_count()

    def render_entries_list():
        """Render the entries list."""
        nonlocal entries_container, pagination_container
        load_entries()

        if entries_container:
            entries_container.clear()

        with entries_container:
            if not state["entries"]:
                ui.label("Журнал заморозок пуст").classes("text-slate-400 text-center py-8")
                return

            for entry in state["entries"]:
                account_info = entry.get("account_info", {})
                analysis = entry.get("analysis", {})

                with ui.card().classes(
                    "w-full bg-slate-800 hover:bg-slate-700 cursor-pointer mb-2"
                ).on("click", lambda e=entry: show_detail(e)):
                    with ui.row().classes("w-full items-center justify-between"):
                        with ui.column().classes("gap-1"):
                            with ui.row().classes("items-center gap-2"):
                                ui.label(f"Session {entry.get('session_id')}").classes(
                                    "text-white font-bold"
                                )
                                if account_info.get("phone_number"):
                                    ui.label(account_info["phone_number"]).classes(
                                        "text-slate-400 text-sm"
                                    )

                            with ui.row().classes("gap-2 items-center"):
                                # Stage badge
                                stage = account_info.get("warmup_stage", 0)
                                ui.badge(f"Stage {stage}", color="blue").props("dense")

                                # Warmups count
                                warmups = account_info.get("total_warmups", 0)
                                ui.label(f"{warmups} warmups").classes("text-slate-400 text-xs")

                                # Provider
                                provider = account_info.get("provider")
                                if provider:
                                    ui.label(f"| {provider}").classes("text-slate-500 text-xs")

                        with ui.column().classes("items-end gap-1"):
                            # Freeze time
                            freeze_time = entry.get("freeze_detected_at", "")
                            ui.label(relative_time(freeze_time)).classes("text-slate-400 text-sm")

                            # Analysis tags
                            patterns = analysis.get("suspicious_patterns", [])
                            if patterns:
                                with ui.row().classes("gap-1"):
                                    for pattern in patterns[:2]:
                                        color = "red" if pattern == "no_real_activity" else "orange"
                                        ui.badge(pattern.replace("_", " "), color=color).props("dense outline")

        # Pagination
        if pagination_container:
            pagination_container.clear()

        with pagination_container:
            total_pages = max(1, (state["total"] + state["page_size"] - 1) // state["page_size"])

            ui.label(f"Всего: {state['total']}").classes("text-slate-400")

            with ui.row().classes("items-center gap-2"):
                def prev_page():
                    if state["page"] > 0:
                        state["page"] -= 1
                        render_entries_list()

                def next_page():
                    if state["page"] < total_pages - 1:
                        state["page"] += 1
                        render_entries_list()

                ui.button(icon="chevron_left", on_click=prev_page).props(
                    "flat dense"
                ).set_enabled(state["page"] > 0)

                ui.label(f"{state['page'] + 1} / {total_pages}").classes(
                    "text-white min-w-16 text-center"
                )

                ui.button(icon="chevron_right", on_click=next_page).props(
                    "flat dense"
                ).set_enabled(state["page"] < total_pages - 1)

    def show_detail(entry: dict):
        """Show detailed view of a freeze entry."""
        nonlocal detail_container
        state["selected_entry"] = entry

        if detail_container:
            detail_container.clear()

        with detail_container:
            account_info = entry.get("account_info", {})
            analysis = entry.get("analysis", {})
            action_stats = entry.get("action_stats", {})
            last_actions = entry.get("last_actions", [])
            admin_data = entry.get("admin_api_data", {})

            # Header
            with ui.row().classes("w-full items-center justify-between mb-4"):
                ui.label(f"Session {entry.get('session_id')}").classes(
                    "text-xl font-bold text-white"
                )
                ui.button(icon="close", on_click=clear_detail).props("flat dense")

            # Account info card
            with card("Account Info").classes("w-full mb-4"):
                with ui.grid(columns=2).classes("gap-4"):
                    ui.label(f"Phone: {account_info.get('phone_number', 'N/A')}").classes("text-white")
                    ui.label(f"Stage: {account_info.get('warmup_stage', 'N/A')}").classes("text-white")
                    ui.label(f"Total Warmups: {account_info.get('total_warmups', 'N/A')}").classes("text-white")
                    ui.label(f"Country: {account_info.get('country', 'N/A')}").classes("text-white")
                    ui.label(f"Provider: {account_info.get('provider', 'N/A')}").classes("text-white")
                    ui.label(f"Type: {account_info.get('account_type', 'N/A')}").classes("text-white")

                ui.separator().classes("my-2")

                ui.label(f"First warmup: {account_info.get('first_warmup_date', 'N/A')}").classes("text-slate-400 text-sm")
                ui.label(f"Last warmup: {account_info.get('last_warmup_date', 'N/A')}").classes("text-slate-400 text-sm")
                ui.label(f"Freeze detected: {entry.get('freeze_detected_at', 'N/A')}").classes("text-slate-400 text-sm")

            # Admin API data (if available)
            if admin_data:
                with card("Admin API Data").classes("w-full mb-4"):
                    with ui.row().classes("gap-4 flex-wrap"):
                        ui.label(f"Status: {admin_data.get('status', 'N/A')}").classes("text-white")
                        ui.label(f"Frozen: {admin_data.get('frozen', 'N/A')}").classes("text-white")
                        if admin_data.get('ban_date'):
                            ui.label(f"Ban date: {admin_data.get('ban_date')}").classes("text-red-400")

            # Analysis card
            with card("Analysis").classes("w-full mb-4"):
                with ui.row().classes("gap-4 mb-2"):
                    ui.badge(
                        f"Age: {analysis.get('account_age_category', 'unknown')}",
                        color="blue"
                    )
                    ui.badge(
                        f"Activity: {analysis.get('activity_level', 'unknown')}",
                        color="green"
                    )

                patterns = analysis.get("suspicious_patterns", [])
                if patterns:
                    ui.label("Suspicious Patterns:").classes("text-slate-400 mt-2")
                    with ui.row().classes("gap-2 flex-wrap"):
                        for pattern in patterns:
                            ui.badge(pattern.replace("_", " "), color="red").props("outline")

                recommendations = analysis.get("recommendations", [])
                if recommendations:
                    ui.label("Recommendations:").classes("text-slate-400 mt-2")
                    for rec in recommendations:
                        ui.label(f"  - {rec}").classes("text-yellow-400 text-sm")

            # Action stats card
            with card("Action Statistics").classes("w-full mb-4"):
                if action_stats:
                    total = sum(action_stats.values())
                    with ui.row().classes("gap-4 flex-wrap"):
                        for action_type, count in sorted(
                            action_stats.items(),
                            key=lambda x: x[1],
                            reverse=True
                        ):
                            pct = count / total * 100 if total > 0 else 0
                            ui.badge(
                                f"{action_type}: {count} ({pct:.0f}%)",
                                color=action_type_color(action_type)
                            )
                else:
                    ui.label("No action history").classes("text-slate-400")

            # Last actions card
            with card("Last 30 Actions (newest first)").classes("w-full"):
                if last_actions:
                    with ui.scroll_area().classes("w-full").style("max-height: 400px"):
                        for action in last_actions:
                            with ui.row().classes("w-full items-center gap-2 py-1 border-b border-slate-700"):
                                ui.label(action.get("timestamp", "")[:19]).classes(
                                    "text-slate-500 text-xs font-mono w-36"
                                )
                                ui.badge(
                                    action.get("action_type", "unknown"),
                                    color=action_type_color(action.get("action_type", ""))
                                ).props("dense")

                                # Show action data preview
                                action_data = action.get("action_data")
                                if action_data and isinstance(action_data, dict):
                                    preview = ""
                                    if "channel" in action_data:
                                        preview = f"-> {action_data['channel']}"
                                    elif "chat_id" in action_data:
                                        preview = f"-> chat:{action_data['chat_id']}"
                                    elif "bot" in action_data:
                                        preview = f"-> {action_data['bot']}"
                                    if preview:
                                        ui.label(preview).classes("text-slate-400 text-xs")
                else:
                    ui.label("No actions recorded").classes("text-slate-400")

    def clear_detail():
        """Clear detail view."""
        nonlocal detail_container
        state["selected_entry"] = None
        if detail_container:
            detail_container.clear()
            with detail_container:
                ui.label("Select an entry to view details").classes(
                    "text-slate-400 text-center py-8"
                )

    def backfill_history():
        """Backfill journal for existing frozen accounts."""
        try:
            from freeze_journal import record_existing_frozen_accounts
            count = record_existing_frozen_accounts()
            ui.notify(f"Recorded {count} historical freeze events", type="positive")
            render_entries_list()
        except Exception as e:
            ui.notify(f"Error: {e}", type="negative")

    def content():
        nonlocal entries_container, detail_container, pagination_container

        # Header with actions
        with ui.row().classes("w-full items-center justify-between mb-4"):
            ui.label("").classes("text-xl")  # Spacer for layout consistency

            with ui.row().classes("gap-2"):
                ui.button(
                    "Backfill History",
                    icon="history",
                    on_click=backfill_history
                ).props("flat").tooltip("Record journal entries for existing frozen accounts")

        # Main content - two columns
        with ui.row().classes("w-full gap-4"):
            # Left column - entries list
            with ui.column().classes("w-1/3"):
                with card("Frozen Accounts").classes("w-full"):
                    entries_container = ui.column().classes("w-full")
                    pagination_container = ui.row().classes(
                        "items-center justify-between mt-4 w-full"
                    )

            # Right column - detail view
            with ui.column().classes("w-2/3"):
                with card("Details").classes("w-full"):
                    detail_container = ui.column().classes("w-full")
                    with detail_container:
                        ui.label("Select an entry to view details").classes(
                            "text-slate-400 text-center py-8"
                        )

        # Initial load
        render_entries_list()

    def refresh():
        render_entries_list()
        ui.notify("Data refreshed", type="positive")

    page_layout("Freeze Journal", content, refresh_callback=refresh)
