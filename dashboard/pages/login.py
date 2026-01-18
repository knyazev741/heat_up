"""
Login page for dashboard authentication.
"""

from nicegui import ui, app
from dashboard.auth import login, is_authenticated
from dashboard.components.layout import get_base_path


def create_login_page():
    """Create the login page."""

    # Redirect if already authenticated
    if is_authenticated():
        ui.navigate.to(f"{get_base_path()}/")
        return

    # Dark theme
    ui.dark_mode().enable()
    ui.query("body").classes("bg-slate-950")

    # Center the login form
    with ui.column().classes("items-center justify-center min-h-screen w-full"):
        with ui.card().classes("bg-slate-800 border border-slate-700 p-8 w-96"):
            # Logo and title
            with ui.column().classes("items-center mb-6"):
                ui.icon("local_fire_department").classes("text-6xl text-orange-500")
                ui.label("Heat Up").classes("text-2xl font-bold text-white mt-2")
                ui.label("Dashboard").classes("text-slate-400")

            # Password input
            password_input = ui.input(
                label="Пароль",
                password=True,
                password_toggle_button=True
            ).classes("w-full").props("dark outlined")

            # Error message
            error_label = ui.label("").classes("text-red-400 text-sm h-6")

            # Login button
            async def do_login():
                password = password_input.value
                if not password:
                    error_label.text = "Введите пароль"
                    return

                if login(password):
                    ui.navigate.to(f"{get_base_path()}/")
                else:
                    error_label.text = "Неверный пароль"
                    password_input.value = ""

            ui.button(
                "Войти",
                on_click=do_login
            ).classes("w-full mt-4").props("color=primary")

            # Handle Enter key
            password_input.on("keydown.enter", do_login)

        # Footer
        ui.label("Heat Up Telegram Warmup Service").classes("text-slate-600 text-sm mt-8")
