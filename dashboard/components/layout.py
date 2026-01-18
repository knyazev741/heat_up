"""
Common layout components for dashboard.
Includes sidebar navigation, header, and page wrapper.
"""

import os
from nicegui import ui, app
from datetime import datetime
from typing import Callable, Optional
import asyncio

from dashboard.auth import is_authenticated, logout


def get_base_path() -> str:
    """Get base path for dashboard URLs.

    When using mount_path in ui.run_with(), NiceGUI handles the prefix automatically
    for navigation. So we return empty string for integrated mode.
    Only standalone mode needs the base path.
    """
    # When integrated via mount_path, NiceGUI handles prefix internally
    # Return empty for both modes - navigation is relative
    return ""


def get_nav_items():
    """Get navigation items with correct base path."""
    base = get_base_path()
    return [
        {"path": f"{base}/", "icon": "dashboard", "label": "Обзор"},
        {"path": f"{base}/accounts", "icon": "people", "label": "Аккаунты"},
        {"path": f"{base}/connections", "icon": "hub", "label": "Связи"},
        {"path": f"{base}/channels", "icon": "forum", "label": "Каналы"},
        {"path": f"{base}/logs", "icon": "history", "label": "Логи"},
        {"path": f"{base}/settings", "icon": "settings", "label": "Настройки"},
    ]


def create_header(title: str, refresh_callback: Optional[Callable] = None):
    """Create page header with title and controls."""
    with ui.header().classes("bg-slate-900 items-center justify-between px-6 py-3"):
        with ui.row().classes("items-center gap-4"):
            # Logo/Title
            ui.label("Heat Up").classes("text-xl font-bold text-blue-400")
            ui.label("|").classes("text-slate-500")
            ui.label(title).classes("text-lg text-white")

        with ui.row().classes("items-center gap-4"):
            # Current time
            time_label = ui.label().classes("text-slate-400 text-sm")

            async def update_time():
                while True:
                    time_label.text = datetime.now().strftime("%H:%M:%S")
                    await asyncio.sleep(1)

            ui.timer(1, lambda: time_label.set_text(datetime.now().strftime("%H:%M:%S")))

            # Refresh button
            if refresh_callback:
                ui.button(icon="refresh", on_click=refresh_callback).props(
                    "flat round dense"
                ).classes("text-slate-300")

            # Logout button
            def do_logout():
                logout()
                ui.navigate.to(f"{get_base_path()}/login")

            ui.button(icon="logout", on_click=do_logout).props(
                "flat round dense"
            ).classes("text-slate-300").tooltip("Выйти")


def create_sidebar():
    """Create sidebar navigation."""
    with ui.left_drawer(value=True).classes("bg-slate-800 p-4").props("width=200"):
        ui.label("Навигация").classes("text-slate-400 text-sm mb-4 uppercase tracking-wider")

        for item in get_nav_items():
            with ui.link(target=item["path"]).classes("no-underline"):
                with ui.row().classes(
                    "items-center gap-3 p-3 rounded-lg hover:bg-slate-700 transition-colors cursor-pointer w-full"
                ):
                    ui.icon(item["icon"]).classes("text-slate-400")
                    ui.label(item["label"]).classes("text-white")


def page_layout(title: str, content_func: Callable, refresh_callback: Optional[Callable] = None):
    """
    Wrapper for creating authenticated pages with common layout.

    Usage:
        @ui.page("/")
        def home_page():
            def content():
                ui.label("Hello World")

            page_layout("Home", content)
    """
    # Check auth
    if not is_authenticated():
        ui.navigate.to(f"{get_base_path()}/login")
        return

    # Dark theme
    ui.dark_mode().enable()
    ui.query("body").classes("bg-slate-950")

    # Create layout
    create_header(title, refresh_callback)
    create_sidebar()

    # Main content area
    with ui.column().classes("p-6 w-full min-h-screen"):
        content_func()


def card(title: str, classes: str = ""):
    """Create a styled card container."""
    container = ui.card().classes(f"bg-slate-800 border border-slate-700 p-4 {classes}")
    with container:
        if title:
            ui.label(title).classes("text-lg font-semibold text-white mb-4")
    return container


def section_title(text: str):
    """Create a section title."""
    ui.label(text).classes("text-xl font-bold text-white mb-4")


def badge(text: str, color: str = "gray"):
    """Create a colored badge."""
    color_classes = {
        "green": "bg-green-600 text-white",
        "yellow": "bg-yellow-500 text-black",
        "blue": "bg-blue-600 text-white",
        "purple": "bg-purple-600 text-white",
        "red": "bg-red-600 text-white",
        "orange": "bg-orange-500 text-white",
        "gray": "bg-gray-600 text-white",
        "cyan": "bg-cyan-600 text-white",
        "teal": "bg-teal-600 text-white",
        "indigo": "bg-indigo-600 text-white",
        "pink": "bg-pink-600 text-white",
    }
    classes = color_classes.get(color, color_classes["gray"])
    ui.label(text).classes(f"px-2 py-1 rounded text-xs font-medium {classes}")
