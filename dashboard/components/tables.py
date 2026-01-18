"""
Reusable table components for dashboard.
"""

from nicegui import ui
from typing import List, Dict, Any, Callable, Optional

from dashboard.utils.formatters import (
    relative_time, mask_phone, stage_color, status_badge,
    action_type_label, action_type_color, truncate
)
from dashboard.components.layout import badge


def accounts_table(
    accounts: List[Dict[str, Any]],
    on_click: Optional[Callable[[Dict], None]] = None,
    show_checkbox: bool = False
):
    """
    Create accounts table with standard columns.

    Args:
        accounts: List of account dicts
        on_click: Callback when row is clicked
        show_checkbox: Show selection checkboxes
    """
    columns = [
        {"name": "id", "label": "ID", "field": "id", "align": "left"},
        {"name": "session_id", "label": "Session", "field": "session_id", "align": "left"},
        {"name": "phone", "label": "Телефон", "field": "phone", "align": "left"},
        {"name": "persona", "label": "Персона", "field": "persona_name", "align": "left"},
        {"name": "stage", "label": "Stage", "field": "stage", "align": "center"},
        {"name": "country", "label": "Страна", "field": "country", "align": "center"},
        {"name": "status", "label": "Статус", "field": "status", "align": "center"},
        {"name": "actions", "label": "Действий", "field": "total_actions", "align": "right"},
        {"name": "last_activity", "label": "Активность", "field": "last_activity", "align": "right"},
    ]

    # Transform data for display
    rows = []
    for acc in accounts:
        status_text, status_color = status_badge(
            acc.get("is_active", False),
            acc.get("is_frozen", False),
            acc.get("is_banned", False)
        )
        rows.append({
            "id": acc["id"],
            "session_id": truncate(acc.get("session_id", ""), 12),
            "phone": mask_phone(acc.get("phone")),
            "persona_name": acc.get("persona_name") or "—",
            "stage": acc.get("stage", 1),
            "country": acc.get("country") or "—",
            "status": status_text,
            "status_color": status_color,
            "total_actions": acc.get("total_actions", 0),
            "last_activity": relative_time(acc.get("last_activity")),
            "_raw": acc
        })

    table = ui.table(
        columns=columns,
        rows=rows,
        row_key="id",
        selection="multiple" if show_checkbox else None,
    ).classes("w-full bg-slate-800")

    # Custom cell rendering
    table.add_slot(
        "body-cell-stage",
        """
        <q-td :props="props">
            <q-badge :color="props.row.stage <= 3 ? 'green' : props.row.stage <= 6 ? 'yellow' : props.row.stage <= 9 ? 'blue' : 'purple'">
                {{ props.row.stage }}
            </q-badge>
        </q-td>
        """
    )

    table.add_slot(
        "body-cell-status",
        """
        <q-td :props="props">
            <q-badge :color="props.row.status_color">
                {{ props.row.status }}
            </q-badge>
        </q-td>
        """
    )

    if on_click:
        table.on("row-click", lambda e: on_click(e.args[1]["_raw"]))

    return table


def actions_table(actions: List[Dict[str, Any]], compact: bool = False):
    """
    Create actions/history table.

    Args:
        actions: List of action dicts
        compact: Use compact layout
    """
    columns = [
        {"name": "timestamp", "label": "Время", "field": "timestamp", "align": "left"},
        {"name": "account", "label": "Аккаунт", "field": "persona_name", "align": "left"},
        {"name": "action_type", "label": "Тип", "field": "action_type", "align": "left"},
        {"name": "details", "label": "Детали", "field": "details", "align": "left"},
    ]

    if compact:
        columns = columns[:3]  # Only time, account, type

    rows = []
    for action in actions:
        # Extract details from action_data
        details = ""
        action_data = action.get("action_data", {})
        if isinstance(action_data, dict):
            if "channel" in action_data:
                details = f"Канал: {action_data['channel']}"
            elif "message" in action_data:
                details = truncate(action_data["message"], 40)
            elif "error" in action_data:
                details = f"Ошибка: {truncate(action_data['error'], 40)}"

        rows.append({
            "id": action.get("id"),
            "timestamp": relative_time(action.get("timestamp")),
            "persona_name": action.get("persona_name") or action.get("session_id", "")[:10],
            "action_type": action_type_label(action.get("action_type", "")),
            "action_type_raw": action.get("action_type", ""),
            "details": details or "—",
        })

    table = ui.table(
        columns=columns,
        rows=rows,
        row_key="id",
    ).classes("w-full bg-slate-800")

    return table


def simple_table(
    data: List[Dict[str, Any]],
    columns: List[Dict[str, str]],
    row_key: str = "id",
    on_click: Optional[Callable[[Dict], None]] = None
):
    """
    Create a simple generic table.

    Args:
        data: List of row dicts
        columns: Column definitions [{"name": "col", "label": "Label", "field": "col"}]
        row_key: Unique row identifier field
        on_click: Optional row click handler
    """
    table = ui.table(
        columns=columns,
        rows=data,
        row_key=row_key,
    ).classes("w-full bg-slate-800")

    if on_click:
        table.on("row-click", lambda e: on_click(e.args[1]))

    return table


def paginated_table(
    fetch_func: Callable[[int, int], tuple[List[Dict], int]],
    columns: List[Dict[str, str]],
    row_key: str = "id",
    page_size: int = 25,
    on_click: Optional[Callable[[Dict], None]] = None
):
    """
    Create a paginated table with server-side data fetching.

    Args:
        fetch_func: Function(offset, limit) -> (rows, total)
        columns: Column definitions
        row_key: Unique row identifier
        page_size: Rows per page
        on_click: Row click handler
    """
    current_page = {"value": 0}
    total_rows = {"value": 0}
    table_container = ui.column().classes("w-full")

    def refresh():
        rows, total = fetch_func(current_page["value"] * page_size, page_size)
        total_rows["value"] = total
        table_container.clear()

        with table_container:
            table = ui.table(
                columns=columns,
                rows=rows,
                row_key=row_key,
            ).classes("w-full bg-slate-800")

            if on_click:
                table.on("row-click", lambda e: on_click(e.args[1]))

            # Pagination controls
            total_pages = (total + page_size - 1) // page_size
            with ui.row().classes("items-center justify-between mt-4"):
                ui.label(f"Всего: {total}").classes("text-slate-400")

                with ui.row().classes("items-center gap-2"):
                    ui.button(
                        icon="chevron_left",
                        on_click=lambda: (
                            current_page.update({"value": max(0, current_page["value"] - 1)}),
                            refresh()
                        )
                    ).props("flat dense").bind_enabled_from(
                        current_page, "value", lambda v: v > 0
                    )

                    ui.label(f"{current_page['value'] + 1} / {total_pages}").classes("text-white")

                    ui.button(
                        icon="chevron_right",
                        on_click=lambda: (
                            current_page.update({"value": min(total_pages - 1, current_page["value"] + 1)}),
                            refresh()
                        )
                    ).props("flat dense").bind_enabled_from(
                        current_page, "value", lambda v: v < total_pages - 1
                    )

    refresh()
    return table_container, refresh
