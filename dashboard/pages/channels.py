"""
Channels page showing discovered chats, bot groups, and real chat participation.
"""

from nicegui import ui

from dashboard.auth import is_authenticated
from dashboard.components.layout import page_layout, card, badge
from dashboard.utils.queries import (
    get_discovered_chats_aggregated, get_bot_groups,
    get_real_chat_participation_aggregated
)
from dashboard.utils.formatters import relative_time, format_number


def create_channels_page():
    """Create the channels page with tabs."""

    # Data containers
    data = {
        "discovered": [],
        "bot_groups": [],
        "real_participation": []
    }

    def load_data():
        """Load all channel data."""
        data["discovered"] = get_discovered_chats_aggregated()
        data["bot_groups"] = get_bot_groups()
        data["real_participation"] = get_real_chat_participation_aggregated()

    def content():
        load_data()

        # Tabs
        with ui.tabs().classes("w-full") as tabs:
            tab_discovered = ui.tab("Discovered Chats")
            tab_groups = ui.tab("Bot Groups")
            tab_real = ui.tab("Real Chat Participation")

        with ui.tab_panels(tabs, value=tab_discovered).classes("w-full"):
            # Discovered Chats Tab
            with ui.tab_panel(tab_discovered):
                with card("Найденные каналы и чаты").classes("w-full"):
                    if data["discovered"]:
                        columns = [
                            {"name": "username", "label": "Канал/Чат", "field": "username", "align": "left"},
                            {"name": "title", "label": "Название", "field": "title", "align": "left"},
                            {"name": "type", "label": "Тип", "field": "type", "align": "center"},
                            {"name": "members", "label": "Участников", "field": "members", "align": "right"},
                            {"name": "discovered", "label": "Обнаружен", "field": "discovered_by", "align": "right"},
                            {"name": "joined", "label": "Вступили", "field": "joined_by", "align": "right"},
                            {"name": "relevance", "label": "Релевантность", "field": "relevance", "align": "right"},
                        ]

                        rows = []
                        for chat in data["discovered"]:  # Show all, no limit
                            # Remove @ prefix if present to avoid double @
                            username = chat['username'].lstrip('@') if chat.get('username') else ''
                            rows.append({
                                "username": f"@{username}" if username else "—",
                                "title": chat.get("title") or "—",
                                "type": chat.get("type") or "channel",
                                "members": format_number(chat.get("members")),
                                "discovered_by": chat.get("discovered_by", 0),
                                "joined_by": chat.get("joined_by", 0),
                                "relevance": f"{chat['relevance']:.0%}" if chat.get("relevance") else "—"
                            })

                        table = ui.table(
                            columns=columns,
                            rows=rows,
                            row_key="username",
                            pagination={"rowsPerPage": 25}
                        ).classes("w-full").style("max-height: 500px")

                        table.add_slot(
                            "body-cell-type",
                            """
                            <q-td :props="props">
                                <q-badge :color="props.row.type === 'channel' ? 'blue' : props.row.type === 'supergroup' ? 'green' : 'gray'">
                                    {{ props.row.type }}
                                </q-badge>
                            </q-td>
                            """
                        )

                        ui.label(f"Всего: {len(data['discovered'])} каналов/чатов").classes("text-slate-400 mt-4")
                    else:
                        ui.label("Нет данных").classes("text-slate-400")

            # Bot Groups Tab
            with ui.tab_panel(tab_groups):
                with card("Приватные группы ботов").classes("w-full"):
                    if data["bot_groups"]:
                        columns = [
                            {"name": "id", "label": "ID", "field": "id", "align": "left"},
                            {"name": "title", "label": "Название", "field": "title", "align": "left"},
                            {"name": "type", "label": "Тип", "field": "type", "align": "center"},
                            {"name": "topic", "label": "Тема", "field": "topic", "align": "left"},
                            {"name": "members", "label": "Участников", "field": "members", "align": "right"},
                            {"name": "messages", "label": "Сообщений", "field": "messages", "align": "right"},
                            {"name": "status", "label": "Статус", "field": "status", "align": "center"},
                            {"name": "last_activity", "label": "Активность", "field": "last_activity", "align": "right"},
                        ]

                        rows = []
                        for group in data["bot_groups"]:
                            rows.append({
                                "id": group["id"],
                                "title": group.get("title") or f"Группа #{group['id']}",
                                "type": group.get("type") or "friends",
                                "topic": group.get("topic") or "—",
                                "members": group.get("members", 0),
                                "messages": group.get("messages", 0),
                                "status": group.get("status") or "active",
                                "last_activity": relative_time(group.get("last_activity"))
                            })

                        table = ui.table(
                            columns=columns,
                            rows=rows,
                            row_key="id",
                            pagination={"rowsPerPage": 25}
                        ).classes("w-full").style("max-height: 500px")

                        table.add_slot(
                            "body-cell-type",
                            """
                            <q-td :props="props">
                                <q-badge :color="props.row.type === 'thematic' ? 'purple' : props.row.type === 'work' ? 'orange' : 'cyan'">
                                    {{ props.row.type }}
                                </q-badge>
                            </q-td>
                            """
                        )

                        table.add_slot(
                            "body-cell-status",
                            """
                            <q-td :props="props">
                                <q-badge :color="props.row.status === 'active' ? 'green' : 'gray'">
                                    {{ props.row.status }}
                                </q-badge>
                            </q-td>
                            """
                        )

                        ui.label(f"Всего: {len(data['bot_groups'])} групп").classes("text-slate-400 mt-4")
                    else:
                        ui.label("Нет приватных групп").classes("text-slate-400")

            # Real Chat Participation Tab
            with ui.tab_panel(tab_real):
                with card("Участие в реальных чатах").classes("w-full"):
                    if data["real_participation"]:
                        columns = [
                            {"name": "username", "label": "Чат", "field": "username", "align": "left"},
                            {"name": "accounts", "label": "Аккаунтов", "field": "accounts", "align": "right"},
                            {"name": "messages", "label": "Сообщений", "field": "messages", "align": "right"},
                            {"name": "reactions", "label": "Реакций", "field": "reactions", "align": "right"},
                            {"name": "last_activity", "label": "Последняя активность", "field": "last_activity", "align": "right"},
                        ]

                        rows = []
                        for part in data["real_participation"]:
                            # Remove @ prefix if present to avoid double @
                            username = part['username'].lstrip('@') if part.get('username') else ''
                            rows.append({
                                "username": f"@{username}" if username else "—",
                                "accounts": part.get("accounts", 0),
                                "messages": part.get("messages", 0),
                                "reactions": part.get("reactions", 0),
                                "last_activity": relative_time(part.get("last_activity"))
                            })

                        ui.table(
                            columns=columns,
                            rows=rows,
                            row_key="username",
                            pagination={"rowsPerPage": 25}
                        ).classes("w-full").style("max-height: 500px")

                        ui.label(f"Всего: {len(data['real_participation'])} чатов с участием").classes("text-slate-400 mt-4")
                    else:
                        ui.label("Нет данных об участии в реальных чатах").classes("text-slate-400")

    def refresh():
        load_data()
        ui.notify("Данные обновлены", type="positive")

    page_layout("Каналы и чаты", content, refresh_callback=refresh)
