"""
Settings page for system configuration and management.
"""

from nicegui import ui
import os

from dashboard.auth import is_authenticated, hash_password
from dashboard.components.layout import page_layout, card
from dashboard.components.cards import stat_row
from dashboard.utils.queries import cleanup_old_logs


def create_settings_page():
    """Create the settings page."""

    def content():
        with ui.row().classes("w-full gap-6"):
            # Left column - System
            with ui.column().classes("flex-1 gap-4"):
                # Scheduler control
                with card("Scheduler").classes("w-full"):
                    status_container = ui.column().classes("w-full")

                    def refresh_scheduler_status():
                        status_container.clear()
                        with status_container:
                            # Get scheduler status directly from Python
                            try:
                                from main import warmup_scheduler
                                if warmup_scheduler:
                                    status = warmup_scheduler.get_status()
                                    is_running = status.get("is_running", False)
                                else:
                                    is_running = False
                                    status = {}
                            except Exception as e:
                                is_running = False
                                status = {"error": str(e)}

                            status_text = "Запущен" if is_running else "Остановлен"
                            status_color = "green" if is_running else "red"

                            with ui.row().classes("items-center gap-2 mb-4"):
                                ui.icon("circle").classes(f"text-{status_color}-500 text-sm")
                                ui.label(status_text).classes(f"text-{status_color}-400 font-medium")

                            if status.get("next_check_in"):
                                stat_row("Следующая проверка", f"{status['next_check_in'] // 60} мин")
                            if status.get("accounts_scheduled"):
                                stat_row("Активных прогревов", status["accounts_scheduled"])
                            if status.get("helper_accounts"):
                                stat_row("Helper аккаунтов", status["helper_accounts"])
                            if status.get("active_conversations") is not None:
                                stat_row("Активных диалогов", status["active_conversations"])
                            if status.get("active_groups") is not None:
                                stat_row("Активных групп", status["active_groups"])
                            if "error" in status:
                                ui.label(f"Ошибка: {status['error']}").classes("text-red-400 text-sm mt-2")

                            # Control buttons
                            with ui.row().classes("gap-2 mt-4"):
                                async def scheduler_action(action: str):
                                    try:
                                        from main import warmup_scheduler
                                        if action == "start":
                                            await warmup_scheduler.start()
                                            ui.notify("Scheduler запущен", type="positive")
                                        elif action == "stop":
                                            await warmup_scheduler.stop()
                                            ui.notify("Scheduler остановлен", type="positive")
                                    except Exception as e:
                                        ui.notify(f"Ошибка: {e}", type="negative")
                                    refresh_scheduler_status()

                                ui.button(
                                    "Запустить",
                                    icon="play_arrow",
                                    on_click=lambda: scheduler_action("start")
                                ).props("color=green").set_enabled(not is_running)

                                ui.button(
                                    "Остановить",
                                    icon="stop",
                                    on_click=lambda: scheduler_action("stop")
                                ).props("color=red").set_enabled(is_running)

                                ui.button(
                                    "Обновить",
                                    icon="refresh",
                                    on_click=refresh_scheduler_status
                                ).props("flat")

                    refresh_scheduler_status()

                # Main API status
                with card("Компоненты системы").classes("w-full"):
                    api_container = ui.column().classes("w-full")

                    def check_api():
                        api_container.clear()
                        with api_container:
                            try:
                                from main import telegram_client, llm_agent, warmup_scheduler

                                # Check components
                                tg_ok = telegram_client is not None
                                llm_ok = llm_agent is not None
                                scheduler_ok = warmup_scheduler is not None

                                all_ok = tg_ok and llm_ok and scheduler_ok

                                with ui.row().classes("items-center gap-2 mb-2"):
                                    if all_ok:
                                        ui.icon("check_circle").classes("text-green-500")
                                        ui.label("Все компоненты работают").classes("text-green-400")
                                    else:
                                        ui.icon("warning").classes("text-yellow-500")
                                        ui.label("Некоторые компоненты недоступны").classes("text-yellow-400")

                                stat_row("Telegram Client", "✓" if tg_ok else "✗")
                                stat_row("LLM Agent", "✓" if llm_ok else "✗")
                                stat_row("Scheduler", "✓" if scheduler_ok else "✗")

                            except Exception as e:
                                with ui.row().classes("items-center gap-2"):
                                    ui.icon("error").classes("text-red-500")
                                    ui.label("Ошибка проверки").classes("text-red-400")
                                ui.label(str(e)).classes("text-slate-400 text-sm")

                    check_api()
                    ui.button("Проверить", icon="refresh", on_click=check_api).props("flat").classes("mt-2")

            # Right column - Password and Data
            with ui.column().classes("flex-1 gap-4"):
                # Change password
                with card("Изменить пароль").classes("w-full"):
                    current_pw = ui.input(
                        "Текущий пароль",
                        password=True,
                        password_toggle_button=True
                    ).classes("w-full").props("dark outlined")

                    new_pw = ui.input(
                        "Новый пароль",
                        password=True,
                        password_toggle_button=True
                    ).classes("w-full").props("dark outlined")

                    confirm_pw = ui.input(
                        "Подтвердите пароль",
                        password=True,
                        password_toggle_button=True
                    ).classes("w-full").props("dark outlined")

                    result_label = ui.label("").classes("text-sm h-6")

                    def change_password():
                        if not current_pw.value or not new_pw.value:
                            result_label.text = "Заполните все поля"
                            result_label.classes(remove="text-green-400", add="text-red-400")
                            return

                        if new_pw.value != confirm_pw.value:
                            result_label.text = "Пароли не совпадают"
                            result_label.classes(remove="text-green-400", add="text-red-400")
                            return

                        if len(new_pw.value) < 4:
                            result_label.text = "Пароль слишком короткий"
                            result_label.classes(remove="text-green-400", add="text-red-400")
                            return

                        # Verify current password
                        from dashboard.auth import verify_password
                        if not verify_password(current_pw.value):
                            result_label.text = "Неверный текущий пароль"
                            result_label.classes(remove="text-green-400", add="text-red-400")
                            return

                        # Generate new hash
                        new_hash = hash_password(new_pw.value)

                        # Update .env
                        try:
                            env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
                            env_path = os.path.abspath(env_path)

                            # Read current .env
                            lines = []
                            hash_found = False
                            if os.path.exists(env_path):
                                with open(env_path, "r") as f:
                                    for line in f:
                                        if line.startswith("DASHBOARD_PASSWORD_HASH="):
                                            lines.append(f"DASHBOARD_PASSWORD_HASH={new_hash}\n")
                                            hash_found = True
                                        else:
                                            lines.append(line)

                            if not hash_found:
                                lines.append(f"\nDASHBOARD_PASSWORD_HASH={new_hash}\n")

                            with open(env_path, "w") as f:
                                f.writelines(lines)

                            # Update environment variable
                            os.environ["DASHBOARD_PASSWORD_HASH"] = new_hash

                            result_label.text = "Пароль успешно изменён"
                            result_label.classes(remove="text-red-400", add="text-green-400")

                            # Clear inputs
                            current_pw.value = ""
                            new_pw.value = ""
                            confirm_pw.value = ""

                        except Exception as e:
                            result_label.text = f"Ошибка: {e}"
                            result_label.classes(remove="text-green-400", add="text-red-400")

                    ui.button("Изменить пароль", on_click=change_password).props("color=primary")

                # Data management
                with card("Управление данными").classes("w-full"):
                    # Download database
                    ui.label("Экспорт базы данных").classes("text-slate-400 text-sm mb-2")

                    def download_db():
                        db_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "sessions.db")
                        db_path = os.path.abspath(db_path)
                        if os.path.exists(db_path):
                            with open(db_path, "rb") as f:
                                ui.download(f.read(), "sessions.db")
                        else:
                            ui.notify("База данных не найдена", type="negative")

                    ui.button("Скачать sessions.db", icon="download", on_click=download_db).props("flat")

                    ui.separator().classes("my-4")

                    # Cleanup logs
                    ui.label("Очистка старых логов").classes("text-slate-400 text-sm mb-2")

                    with ui.row().classes("items-end gap-2"):
                        days_input = ui.number(
                            "Старше (дней)",
                            value=30,
                            min=1,
                            max=365
                        ).classes("w-32").props("dark outlined dense")

                        cleanup_result = ui.label("").classes("text-sm")

                        def do_cleanup():
                            days = int(days_input.value or 30)
                            try:
                                deleted = cleanup_old_logs(days)
                                cleanup_result.text = f"Удалено {deleted} записей"
                                cleanup_result.classes(remove="text-red-400", add="text-green-400")
                            except Exception as e:
                                cleanup_result.text = f"Ошибка: {e}"
                                cleanup_result.classes(remove="text-green-400", add="text-red-400")

                        ui.button("Очистить", icon="delete_sweep", on_click=do_cleanup).props("color=red flat")

                # System info
                with card("Информация о системе").classes("w-full"):
                    import platform
                    import sys

                    stat_row("Python", sys.version.split()[0])
                    stat_row("Платформа", platform.system())
                    stat_row("Dashboard порт", "8081")
                    stat_row("API порт", "8080")

    page_layout("Настройки", content)
