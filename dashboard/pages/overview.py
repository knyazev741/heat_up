"""
Overview (main) page showing KPIs and recent activity.
"""

from nicegui import ui

from dashboard.auth import is_authenticated
from dashboard.components.layout import page_layout, card, get_base_path
from dashboard.components.cards import kpi_card
from dashboard.components.charts import country_pie_chart, activity_line_chart
from dashboard.components.tables import accounts_table, actions_table
from dashboard.utils.queries import (
    get_kpi_stats, get_ready_accounts_count, get_country_distribution,
    get_activity_by_day, get_recent_accounts, get_recent_actions
)


def create_overview_page():
    """Create the main overview page."""

    # Data containers for refresh
    data = {
        "kpi": {},
        "ready_count": 0,
        "countries": [],
        "activity": [],
        "recent_accounts": [],
        "recent_actions": []
    }

    def load_data():
        """Load all data for the page."""
        data["kpi"] = get_kpi_stats()
        data["ready_count"] = get_ready_accounts_count()
        data["countries"] = get_country_distribution()
        data["activity"] = get_activity_by_day(14)
        data["recent_accounts"] = get_recent_accounts(5)
        data["recent_actions"] = get_recent_actions(10)

    # Content containers for refresh
    content_container = None

    def build_content():
        """Build page content."""
        nonlocal content_container
        load_data()

        if content_container:
            content_container.clear()
        else:
            content_container = ui.column().classes("w-full gap-6")

        with content_container:
            # KPI Cards Row
            with ui.row().classes("w-full gap-4 flex-wrap"):
                kpi_card(
                    "Всего аккаунтов",
                    data["kpi"].get("total_accounts", 0),
                    color="blue",
                    icon="people"
                )
                kpi_card(
                    "Активных (warmup)",
                    data["kpi"].get("active_warmup", 0),
                    color="green",
                    icon="trending_up"
                )
                kpi_card(
                    "Готовых к работе",
                    data["ready_count"],
                    color="purple",
                    icon="verified"
                )
                kpi_card(
                    "Helper аккаунтов",
                    data["kpi"].get("helpers", 0),
                    color="cyan",
                    icon="support_agent"
                )
                kpi_card(
                    "Действий сегодня",
                    data["kpi"].get("actions_today", 0),
                    color="orange",
                    icon="bolt"
                )

            # Charts Row
            with ui.row().classes("w-full gap-4"):
                # Country distribution pie chart (warmup only)
                with card("Warmup по странам").classes("flex-1"):
                    country_pie_chart(data["countries"])

                # Activity line chart
                with card("Активность за 14 дней").classes("flex-1"):
                    activity_line_chart(data["activity"])

            # Tables Row
            with ui.row().classes("w-full gap-4"):
                # Recent accounts
                with card("Последние аккаунты").classes("flex-1"):
                    if data["recent_accounts"]:
                        columns = [
                            {"name": "id", "label": "ID", "field": "id", "align": "left"},
                            {"name": "persona", "label": "Персона", "field": "persona_name", "align": "left"},
                            {"name": "stage", "label": "Stage", "field": "stage", "align": "center"},
                            {"name": "type", "label": "Тип", "field": "type", "align": "center"},
                        ]
                        rows = [
                            {
                                "id": acc["id"],
                                "persona_name": acc.get("persona_name") or "—",
                                "stage": acc.get("stage", 1),
                                "type": acc.get("type", "warmup")
                            }
                            for acc in data["recent_accounts"]
                        ]
                        table = ui.table(columns=columns, rows=rows, row_key="id").classes("w-full")
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
                        base = get_base_path()
                        table.on("row-click", lambda e: ui.navigate.to(f"{get_base_path()}/accounts/{e.args[1]['id']}"))
                    else:
                        ui.label("Нет аккаунтов").classes("text-slate-400")

                    ui.link("Все аккаунты →", f"{get_base_path()}/accounts").classes("text-blue-400 mt-2")

                # Recent actions
                with card("Последние действия").classes("flex-1"):
                    if data["recent_actions"]:
                        actions_table(data["recent_actions"], compact=True)
                    else:
                        ui.label("Нет действий").classes("text-slate-400")

                    ui.link("Все логи →", f"{get_base_path()}/logs").classes("text-blue-400 mt-2")

    def refresh():
        """Refresh all data on the page."""
        build_content()
        ui.notify("Данные обновлены", type="positive")

    def content():
        build_content()
        # Auto-refresh every 60 seconds (reduced to improve connection stability)
        ui.timer(60, build_content)

    page_layout("Обзор", content, refresh_callback=refresh)
