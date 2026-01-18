"""
Accounts page with list, detail view, and add functionality.
"""

from nicegui import ui
import json

from dashboard.auth import is_authenticated
from dashboard.components.layout import page_layout, card, badge, get_base_path
from dashboard.components.cards import kpi_card, stat_row, progress_bar, info_card
from dashboard.components.tables import simple_table
from dashboard.utils.queries import (
    get_accounts, get_account_details, get_account_connections,
    get_account_chats, get_account_history, get_countries
)
from dashboard.utils.formatters import (
    relative_time, mask_phone, stage_color, status_badge,
    action_type_label, truncate
)


def create_accounts_list_page():
    """Create the accounts list page."""

    # State
    state = {
        "search": "",
        "account_type": "all",
        "stages": [],
        "status": "all",
        "country": "",
        "page": 0,
        "page_size": 25,
        "accounts": [],
        "total": 0
    }

    table_container = None
    pagination_container = None

    def load_accounts():
        """Load accounts with current filters."""
        accounts, total = get_accounts(
            search=state["search"],
            account_type=state["account_type"],
            stages=state["stages"] if state["stages"] else None,
            status=state["status"],
            country=state["country"],
            limit=state["page_size"],
            offset=state["page"] * state["page_size"]
        )
        state["accounts"] = accounts
        state["total"] = total

    def render_table():
        """Render the accounts table."""
        nonlocal table_container, pagination_container
        load_accounts()

        if table_container:
            table_container.clear()

        with table_container:
            if not state["accounts"]:
                ui.label("Аккаунты не найдены").classes("text-slate-400 text-center py-8")
                return

            columns = [
                {"name": "id", "label": "ID", "field": "id", "align": "left", "sortable": True},
                {"name": "session_id", "label": "Session", "field": "session_id", "align": "left"},
                {"name": "phone", "label": "Телефон", "field": "phone", "align": "left"},
                {"name": "persona_name", "label": "Персона", "field": "persona_name", "align": "left"},
                {"name": "stage", "label": "Stage", "field": "stage", "align": "center", "sortable": True},
                {"name": "country", "label": "Страна", "field": "country", "align": "center"},
                {"name": "status", "label": "Статус", "field": "status", "align": "center"},
                {"name": "total_actions", "label": "Действий", "field": "total_actions", "align": "right", "sortable": True},
                {"name": "last_activity", "label": "Активность", "field": "last_activity", "align": "right"},
            ]

            rows = []
            for acc in state["accounts"]:
                status_text, status_clr = status_badge(
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
                    "status_color": status_clr,
                    "total_actions": acc.get("total_actions", 0),
                    "last_activity": relative_time(acc.get("last_activity")),
                })

            table = ui.table(
                columns=columns,
                rows=rows,
                row_key="id",
                pagination={"rowsPerPage": 0}  # Disable built-in pagination
            ).classes("w-full")

            # Custom cell rendering for stage
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

            # Row click handler
            table.on("row-click", lambda e: ui.navigate.to(f"{get_base_path()}/accounts/{e.args[1]['id']}"))

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
        """Apply filters and refresh table."""
        state["page"] = 0
        render_table()

    def show_add_dialog():
        """Show dialog to add new account."""
        with ui.dialog() as dialog, ui.card().classes("bg-slate-800 w-96"):
            ui.label("Добавить аккаунт").classes("text-xl font-bold text-white mb-4")

            session_id = ui.input("Session ID").classes("w-full").props("dark outlined")
            phone = ui.input("Телефон").classes("w-full").props("dark outlined")

            with ui.row().classes("gap-4"):
                acc_type = ui.select(
                    ["warmup", "helper"],
                    value="warmup",
                    label="Тип"
                ).classes("flex-1").props("dark outlined")

                country_input = ui.input("Страна").classes("flex-1").props("dark outlined")

            stage = ui.number("Начальный Stage", value=1, min=1, max=10).classes("w-full").props("dark outlined")

            with ui.row().classes("justify-end gap-2 mt-4"):
                ui.button("Отмена", on_click=dialog.close).props("flat")
                ui.button("Добавить", on_click=lambda: ui.notify("Функция в разработке")).props("color=primary")

        dialog.open()

    def content():
        nonlocal table_container, pagination_container

        # Filters row
        with ui.row().classes("w-full gap-4 items-end flex-wrap mb-4"):
            # Search
            search_input = ui.input(
                "Поиск",
                placeholder="Session ID, телефон, персона..."
            ).classes("w-64").props("dark outlined dense")
            search_input.bind_value(state, "search")
            search_input.on("keydown.enter", apply_filters)

            # Type filter
            type_select = ui.select(
                {"all": "Все", "warmup": "Warmup", "helper": "Helper"},
                value="all",
                label="Тип"
            ).classes("w-32").props("dark outlined dense")
            type_select.bind_value(state, "account_type")
            type_select.on("update:model-value", apply_filters)

            # Status filter
            status_select = ui.select(
                {"all": "Все", "active": "Активные", "frozen": "Замороженные", "banned": "Забаненные"},
                value="all",
                label="Статус"
            ).classes("w-36").props("dark outlined dense")
            status_select.bind_value(state, "status")
            status_select.on("update:model-value", apply_filters)

            # Country filter
            countries = get_countries()
            country_options = {"": "Все"} | {c: c for c in countries}
            country_select = ui.select(
                country_options,
                value="",
                label="Страна"
            ).classes("w-32").props("dark outlined dense")
            country_select.bind_value(state, "country")
            country_select.on("update:model-value", apply_filters)

            # Spacer
            ui.element("div").classes("flex-grow")

            # Action buttons
            ui.button("Обновить", icon="refresh", on_click=render_table).props("flat")
            ui.button("Добавить", icon="add", on_click=show_add_dialog).props("color=primary")

        # Table container
        with card("").classes("w-full"):
            table_container = ui.column().classes("w-full")

            # Pagination
            pagination_container = ui.row().classes("items-center justify-between mt-4 w-full")

        # Initial load
        render_table()

        # Auto-refresh
        ui.timer(60, render_table)

    def refresh():
        render_table()
        ui.notify("Данные обновлены", type="positive")

    page_layout("Аккаунты", content, refresh_callback=refresh)


def create_account_detail_page(account_id: int):
    """Create account detail page."""

    account = get_account_details(account_id)

    if not account:
        def content():
            ui.label("Аккаунт не найден").classes("text-xl text-red-400")
            ui.link("← Назад к списку", f"{get_base_path()}/accounts").classes("text-blue-400")

        page_layout("Аккаунт не найден", content)
        return

    def content():
        # Back link
        ui.link("← Назад к списку", f"{get_base_path()}/accounts").classes("text-blue-400 mb-4")

        # Main grid
        with ui.row().classes("w-full gap-4"):
            # Left column - Account info
            with ui.column().classes("flex-1 gap-4"):
                # Account card
                with card("Аккаунт").classes("w-full"):
                    stat_row("Session ID", truncate(account.get("session_id", ""), 20), "key")
                    stat_row("Телефон", mask_phone(account.get("phone_number")), "phone")
                    stat_row("Тип", account.get("account_type", "warmup"), "category")
                    stat_row("Создан", relative_time(account.get("created_at")), "calendar_today")
                    stat_row("Провайдер", account.get("provider") or "—", "business")
                    stat_row("Страна", account.get("country") or "—", "public")

                # Status card
                with card("Статус").classes("w-full"):
                    stage = account.get("warmup_stage", 1)
                    progress_bar(stage, 14, "Warmup Stage", stage_color(stage))

                    status_text, status_clr = status_badge(
                        account.get("is_active", False),
                        account.get("is_frozen", False),
                        account.get("is_banned", False)
                    )
                    with ui.row().classes("items-center gap-2 mt-4"):
                        ui.label("Статус:").classes("text-slate-400")
                        badge(status_text, status_clr)

                    stat_row("Can Initiate DM", "Да" if account.get("can_initiate_dm") else "Нет")
                    stat_row("LLM отключен", "Да" if account.get("llm_generation_disabled") else "Нет")

                # Stats card
                with card("Статистика").classes("w-full"):
                    stat_row("Всего прогревов", account.get("total_warmups", 0), "local_fire_department")
                    stat_row("Всего действий", account.get("total_actions", 0), "bolt")
                    stat_row("Сообщений", account.get("sent_messages_count", 0), "chat")
                    stat_row("Каналов", account.get("joined_channels_count", 0), "forum")
                    stat_row("Диалогов", account.get("conversations_count", 0), "question_answer")

            # Center column - Persona and connections
            with ui.column().classes("flex-1 gap-4"):
                # Persona card
                with card("Персона").classes("w-full"):
                    if account.get("generated_name"):
                        stat_row("Имя", account.get("generated_name"), "person")
                        stat_row("Возраст", account.get("age") or "—", "cake")
                        stat_row("Пол", account.get("gender") or "—")
                        stat_row("Город", account.get("city") or "—", "location_city")
                        stat_row("Профессия", account.get("occupation") or "—", "work")

                        # Interests (JSON array)
                        interests = account.get("interests")
                        if interests:
                            try:
                                if isinstance(interests, str):
                                    interests = json.loads(interests)
                                interests_text = ", ".join(interests[:5]) if isinstance(interests, list) else str(interests)
                            except:
                                interests_text = str(interests)
                            stat_row("Интересы", truncate(interests_text, 40), "interests")

                        # Traits
                        traits = account.get("personality_traits")
                        if traits:
                            try:
                                if isinstance(traits, str):
                                    traits = json.loads(traits)
                                traits_text = ", ".join(traits[:3]) if isinstance(traits, list) else str(traits)
                            except:
                                traits_text = str(traits)
                            stat_row("Черты", truncate(traits_text, 40), "psychology")
                    else:
                        ui.label("Персона не создана").classes("text-slate-400")

                # Connections card
                connections = get_account_connections(account_id)
                with card("Связи (DM)").classes("w-full"):
                    if connections:
                        columns = [
                            {"name": "partner", "label": "Партнёр", "field": "partner_name", "align": "left"},
                            {"name": "direction", "label": "Тип", "field": "direction", "align": "center"},
                            {"name": "messages", "label": "Сообщений", "field": "message_count", "align": "right"},
                            {"name": "last", "label": "Последнее", "field": "last_message_at", "align": "right"},
                        ]
                        rows = [
                            {
                                "partner_name": c.get("partner_name") or f"#{c['partner_account_id']}",
                                "direction": "Исходящий" if c["direction"] == "initiated" else "Входящий",
                                "message_count": c["message_count"],
                                "last_message_at": relative_time(c["last_message_at"])
                            }
                            for c in connections[:10]
                        ]
                        ui.table(columns=columns, rows=rows, row_key="partner_name").classes("w-full")

                        if len(connections) > 10:
                            ui.label(f"+ ещё {len(connections) - 10}").classes("text-slate-400 text-sm mt-2")
                    else:
                        ui.label("Нет связей").classes("text-slate-400")

            # Right column - Chats and groups
            with ui.column().classes("flex-1 gap-4"):
                # Discovered chats
                chats = get_account_chats(account_id)
                with card("Чаты").classes("w-full"):
                    if chats:
                        # Tabs for joined/not joined
                        joined = [c for c in chats if c["is_joined"]]
                        not_joined = [c for c in chats if not c["is_joined"]]

                        with ui.tabs().classes("w-full") as tabs:
                            tab_joined = ui.tab(f"Вступил ({len(joined)})")
                            tab_discovered = ui.tab(f"Найдено ({len(not_joined)})")

                        with ui.tab_panels(tabs, value=tab_joined).classes("w-full"):
                            with ui.tab_panel(tab_joined):
                                if joined:
                                    with ui.scroll_area().classes("w-full").style("max-height: 300px"):
                                        for chat in joined:
                                            username = chat['username'].lstrip('@') if chat.get('username') else ''
                                            with ui.row().classes("items-center justify-between py-2 border-b border-slate-700"):
                                                with ui.column().classes("gap-0"):
                                                    ui.label(chat["title"] or username).classes("text-white text-sm")
                                                    ui.label(f"@{username}" if username else "—").classes("text-slate-500 text-xs")
                                                with ui.row().classes("gap-2"):
                                                    badge(chat["type"] or "chat", "blue")
                                                    msgs = chat.get('messages_sent', 0) or 0
                                                    ui.label(f"{msgs} msgs").classes("text-slate-400 text-xs")
                                else:
                                    ui.label("Нет вступлений").classes("text-slate-400")

                            with ui.tab_panel(tab_discovered):
                                if not_joined:
                                    with ui.scroll_area().classes("w-full").style("max-height: 300px"):
                                        for chat in not_joined:
                                            username = chat['username'].lstrip('@') if chat.get('username') else ''
                                            with ui.row().classes("items-center justify-between py-2 border-b border-slate-700"):
                                                with ui.column().classes("gap-0"):
                                                    ui.label(chat["title"] or username).classes("text-white text-sm")
                                                    ui.label(f"@{username}" if username else "—").classes("text-slate-500 text-xs")
                                                relevance = chat.get("relevance")
                                                if relevance:
                                                    ui.label(f"{relevance:.0%}").classes("text-green-400 text-sm")
                                else:
                                    ui.label("Нет найденных чатов").classes("text-slate-400")
                    else:
                        ui.label("Нет чатов").classes("text-slate-400")

        # History section
        ui.label("История действий").classes("text-xl font-bold text-white mt-6 mb-4")

        history = get_account_history(account_id, limit=50)
        with card("").classes("w-full"):
            if history:
                columns = [
                    {"name": "timestamp", "label": "Время", "field": "timestamp", "align": "left"},
                    {"name": "action_type", "label": "Тип", "field": "action_type", "align": "left"},
                    {"name": "details", "label": "Детали", "field": "details", "align": "left"},
                ]

                rows = []
                for h in history:
                    details = ""
                    data = h.get("action_data", {})
                    if isinstance(data, dict):
                        if "channel" in data:
                            details = f"Канал: {data['channel']}"
                        elif "message" in data:
                            details = truncate(str(data["message"]), 50)
                        elif "error" in data:
                            details = f"Ошибка: {truncate(str(data['error']), 40)}"
                        elif data:
                            details = truncate(str(data), 50)

                    rows.append({
                        "timestamp": relative_time(h["timestamp"]),
                        "action_type": action_type_label(h["action_type"]),
                        "details": details or "—"
                    })

                ui.table(columns=columns, rows=rows, row_key="timestamp").classes("w-full")
            else:
                ui.label("Нет истории").classes("text-slate-400")

    page_layout(f"Аккаунт #{account_id}", content)
