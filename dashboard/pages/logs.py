"""
Global logs page with filtering and search.
"""

from nicegui import ui
from datetime import datetime, timedelta

from dashboard.auth import is_authenticated
from dashboard.components.layout import page_layout, card, badge
from dashboard.utils.queries import get_global_logs, get_action_types
from dashboard.utils.formatters import (
    relative_time, action_type_label, action_type_color, truncate
)
import json


def create_logs_page():
    """Create the global logs page."""

    # State
    state = {
        "start_date": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
        "end_date": datetime.now().strftime("%Y-%m-%d"),
        "action_types": [],
        "search": "",
        "page": 0,
        "page_size": 50,
        "logs": [],
        "total": 0
    }

    table_container = None
    pagination_container = None

    def load_logs():
        """Load logs with current filters."""
        logs, total = get_global_logs(
            start_date=state["start_date"],
            end_date=state["end_date"],
            action_types=state["action_types"] if state["action_types"] else None,
            search=state["search"],
            limit=state["page_size"],
            offset=state["page"] * state["page_size"]
        )
        state["logs"] = logs
        state["total"] = total

    def render_table():
        """Render the logs table."""
        nonlocal table_container, pagination_container
        load_logs()

        if table_container:
            table_container.clear()

        with table_container:
            if not state["logs"]:
                ui.label("Логи не найдены").classes("text-slate-400 text-center py-8")
                return

            columns = [
                {"name": "timestamp", "label": "Время", "field": "timestamp", "align": "left"},
                {"name": "account", "label": "Аккаунт", "field": "account", "align": "left"},
                {"name": "action_type", "label": "Тип", "field": "action_type_label", "align": "left"},
                {"name": "details", "label": "Детали", "field": "details", "align": "left"},
            ]

            rows = []
            for log in state["logs"]:
                # Extract details
                details = ""
                action_data = log.get("action_data", {})
                if isinstance(action_data, dict):
                    if "channel" in action_data:
                        details = f"Канал: {action_data['channel']}"
                    elif "message" in action_data:
                        details = truncate(str(action_data["message"]), 60)
                    elif "error" in action_data:
                        details = f"Ошибка: {truncate(str(action_data['error']), 50)}"
                    elif "chat_username" in action_data:
                        details = f"Чат: @{action_data['chat_username']}"
                    elif action_data:
                        # Show first key-value pair
                        for k, v in action_data.items():
                            details = f"{k}: {truncate(str(v), 50)}"
                            break

                rows.append({
                    "id": log["id"],
                    "timestamp": relative_time(log["timestamp"]),
                    "timestamp_full": log["timestamp"],
                    "account": log.get("persona_name") or (log.get("session_id") or "")[:12],
                    "account_id": log.get("account_id"),
                    "action_type": log["action_type"],
                    "action_type_label": action_type_label(log["action_type"]),
                    "action_type_color": action_type_color(log["action_type"]),
                    "details": details or "—",
                    "action_data": log.get("action_data", {})
                })

            table = ui.table(
                columns=columns,
                rows=rows,
                row_key="id",
                pagination={"rowsPerPage": 0}
            ).classes("w-full cursor-pointer").props("dense")

            # Custom cell for action type with color badge
            table.add_slot(
                "body-cell-action_type",
                """
                <q-td :props="props">
                    <q-badge :color="props.row.action_type_color || 'gray'">
                        {{ props.row.action_type_label }}
                    </q-badge>
                </q-td>
                """
            )

            # Add row template with hover effect
            table.add_slot(
                "body",
                """
                <q-tr :props="props" @click="$parent.$emit('row-click', $event, props.row)" class="cursor-pointer hover:bg-slate-700">
                    <q-td v-for="col in props.cols" :key="col.name" :props="props">
                        <template v-if="col.name === 'action_type'">
                            <q-badge :color="props.row.action_type_color || 'gray'">
                                {{ props.row.action_type_label }}
                            </q-badge>
                        </template>
                        <template v-else>
                            {{ col.value }}
                        </template>
                    </q-td>
                </q-tr>
                """
            )

            # Row click to show details
            def show_details(row):
                with ui.dialog() as dialog, ui.card().classes("bg-slate-800 w-[700px] max-w-[90vw]"):
                    ui.label("Event Details").classes("text-xl font-bold text-white mb-4")

                    with ui.column().classes("gap-2 w-full"):
                        with ui.row().classes("gap-4"):
                            ui.label(f"Time: {row['timestamp_full']}").classes("text-slate-300")
                            ui.label(f"Type: {row['action_type']}").classes("text-slate-300")

                        if row.get("account_id"):
                            ui.label(f"Account: {row['account']} (ID: {row['account_id']})").classes("text-slate-300")

                        ui.separator().classes("my-2")

                        ui.label("Action Data:").classes("text-slate-400")
                        with ui.scroll_area().classes("w-full").style("max-height: 400px"):
                            ui.code(
                                json.dumps(row.get("action_data", {}), indent=2, ensure_ascii=False),
                                language="json"
                            ).classes("w-full bg-slate-900 text-sm")

                    with ui.row().classes("justify-end mt-4"):
                        ui.button("Close", on_click=dialog.close).props("flat color=white")

                dialog.open()

            table.on("row-click", lambda e: show_details(e.args[1]))

        # Update pagination
        if pagination_container:
            pagination_container.clear()
            with pagination_container:
                total_pages = max(1, (state["total"] + state["page_size"] - 1) // state["page_size"])

                ui.label(f"Всего: {state['total']}").classes("text-slate-400")

                with ui.row().classes("items-center gap-2"):
                    def prev_page():
                        if state["page"] > 0:
                            state["page"] -= 1
                            render_table()

                    def next_page():
                        if state["page"] < total_pages - 1:
                            state["page"] += 1
                            render_table()

                    ui.button(icon="chevron_left", on_click=prev_page).props(
                        "flat dense"
                    ).set_enabled(state["page"] > 0)

                    ui.label(f"{state['page'] + 1} / {total_pages}").classes("text-white min-w-16 text-center")

                    ui.button(icon="chevron_right", on_click=next_page).props(
                        "flat dense"
                    ).set_enabled(state["page"] < total_pages - 1)

    def apply_filters():
        """Apply filters and refresh."""
        state["page"] = 0
        render_table()

    def export_logs():
        """Export logs to JSON."""
        import json
        logs, _ = get_global_logs(
            start_date=state["start_date"],
            end_date=state["end_date"],
            action_types=state["action_types"] if state["action_types"] else None,
            search=state["search"],
            limit=1000,
            offset=0
        )
        # Create download
        content = json.dumps(logs, indent=2, ensure_ascii=False, default=str)
        ui.download(content.encode(), f"logs_{state['start_date']}_{state['end_date']}.json")

    def content():
        nonlocal table_container, pagination_container

        # Filters row
        with ui.row().classes("w-full gap-4 items-end flex-wrap mb-4"):
            # Date range
            start_date = ui.input(
                "С даты",
                value=state["start_date"]
            ).classes("w-36").props("dark outlined dense type=date")
            start_date.on("update:model-value", lambda e: state.update({"start_date": e.value}))

            end_date = ui.input(
                "По дату",
                value=state["end_date"]
            ).classes("w-36").props("dark outlined dense type=date")
            end_date.on("update:model-value", lambda e: state.update({"end_date": e.value}))

            # Action type filter
            action_types = get_action_types()
            action_options = {t: action_type_label(t) for t in action_types}
            type_select = ui.select(
                action_options,
                multiple=True,
                label="Тип события"
            ).classes("w-48").props("dark outlined dense use-chips")
            type_select.on("update:model-value", lambda e: state.update({"action_types": list(e.value) if e.value else []}))

            # Search
            search_input = ui.input(
                "Поиск",
                placeholder="Текст в данных..."
            ).classes("w-48").props("dark outlined dense")
            search_input.bind_value(state, "search")
            search_input.on("keydown.enter", apply_filters)

            # Apply button
            ui.button("Применить", icon="filter_list", on_click=apply_filters).props("color=primary")

            # Spacer
            ui.element("div").classes("flex-grow")

            # Export button
            ui.button("Экспорт JSON", icon="download", on_click=export_logs).props("flat")

        # Table
        with card("").classes("w-full"):
            table_container = ui.column().classes("w-full")
            pagination_container = ui.row().classes("items-center justify-between mt-4 w-full")

        # Initial load
        render_table()

    def refresh():
        render_table()
        ui.notify("Данные обновлены", type="positive")

    page_layout("Логи", content, refresh_callback=refresh)
