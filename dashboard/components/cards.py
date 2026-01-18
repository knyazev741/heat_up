"""
KPI Cards and stat display components.
"""

from nicegui import ui
from typing import Optional


def kpi_card(
    title: str,
    value: str | int,
    color: str = "blue",
    icon: Optional[str] = None,
    subtitle: Optional[str] = None
):
    """
    Create a KPI metric card.

    Args:
        title: Card title
        value: Main metric value
        color: Accent color (blue, green, yellow, purple, red, orange)
        icon: Optional material icon name
        subtitle: Optional subtitle text
    """
    color_classes = {
        "blue": "border-blue-500 text-blue-400",
        "green": "border-green-500 text-green-400",
        "yellow": "border-yellow-500 text-yellow-400",
        "purple": "border-purple-500 text-purple-400",
        "red": "border-red-500 text-red-400",
        "orange": "border-orange-500 text-orange-400",
        "cyan": "border-cyan-500 text-cyan-400",
    }

    accent_class = color_classes.get(color, color_classes["blue"])

    with ui.card().classes(
        f"bg-slate-800 border-l-4 {accent_class.split()[0]} p-4 flex-1 min-w-48"
    ):
        with ui.row().classes("items-center justify-between"):
            with ui.column().classes("gap-1"):
                ui.label(title).classes("text-slate-400 text-sm uppercase tracking-wider")
                ui.label(str(value)).classes(f"text-3xl font-bold {accent_class.split()[1]}")
                if subtitle:
                    ui.label(subtitle).classes("text-slate-500 text-xs")

            if icon:
                ui.icon(icon).classes(f"text-4xl {accent_class.split()[1]} opacity-50")


def stat_row(label: str, value: str | int, icon: Optional[str] = None):
    """Create a single stat row for detail cards."""
    with ui.row().classes("items-center justify-between py-2 border-b border-slate-700"):
        with ui.row().classes("items-center gap-2"):
            if icon:
                ui.icon(icon).classes("text-slate-500 text-sm")
            ui.label(label).classes("text-slate-400")
        ui.label(str(value)).classes("text-white font-medium")


def progress_bar(value: int, max_value: int, label: str = "", color: str = "blue"):
    """Create a progress bar with label."""
    percentage = min(100, (value / max_value) * 100) if max_value > 0 else 0

    color_classes = {
        "blue": "bg-blue-500",
        "green": "bg-green-500",
        "yellow": "bg-yellow-500",
        "purple": "bg-purple-500",
    }

    bg_class = color_classes.get(color, color_classes["blue"])

    with ui.column().classes("w-full gap-1"):
        if label:
            with ui.row().classes("justify-between"):
                ui.label(label).classes("text-slate-400 text-sm")
                ui.label(f"{value}/{max_value}").classes("text-slate-400 text-sm")

        with ui.element("div").classes("w-full bg-slate-700 rounded-full h-2"):
            ui.element("div").classes(
                f"{bg_class} h-2 rounded-full transition-all duration-300"
            ).style(f"width: {percentage}%")


def info_card(title: str, items: list[tuple[str, str]], icon: Optional[str] = None):
    """
    Create an info card with multiple labeled values.

    Args:
        title: Card title
        items: List of (label, value) tuples
        icon: Optional header icon
    """
    with ui.card().classes("bg-slate-800 border border-slate-700 p-4"):
        with ui.row().classes("items-center gap-2 mb-4"):
            if icon:
                ui.icon(icon).classes("text-blue-400")
            ui.label(title).classes("text-lg font-semibold text-white")

        for label, value in items:
            stat_row(label, value)
