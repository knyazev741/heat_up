"""
Plotly chart components for dashboard.
"""

from nicegui import ui
import plotly.graph_objects as go
from typing import List, Dict, Any


def stage_pie_chart(data: List[Dict[str, Any]]):
    """
    Create a donut chart showing account distribution by warmup stage.

    Args:
        data: List of dicts with 'stage' and 'count' keys
    """
    if not data:
        ui.label("Нет данных").classes("text-slate-400")
        return

    labels = [f"Stage {d['stage']}" for d in data]
    values = [d["count"] for d in data]

    # Color mapping by stage
    colors = []
    for d in data:
        stage = d["stage"] or 0
        if stage <= 3:
            colors.append("#22c55e")  # green
        elif stage <= 6:
            colors.append("#eab308")  # yellow
        elif stage <= 9:
            colors.append("#3b82f6")  # blue
        else:
            colors.append("#a855f7")  # purple

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.5,
                marker_colors=colors,
                textinfo="label+value",
                textposition="outside",
                textfont=dict(color="white"),
                hoverinfo="label+percent+value",
            )
        ]
    )

    fig.update_layout(
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=30, b=20),
        height=300,
        annotations=[
            dict(
                text="Stages",
                x=0.5,
                y=0.5,
                font_size=16,
                font_color="white",
                showarrow=False,
            )
        ],
    )

    ui.plotly(fig).classes("w-full")


def country_pie_chart(data: List[Dict[str, Any]]):
    """
    Create a donut chart showing account distribution by country.

    Args:
        data: List of dicts with 'country' and 'count' keys
    """
    if not data:
        ui.label("Нет данных").classes("text-slate-400")
        return

    # Take top 8 countries, group rest as "Other"
    sorted_data = sorted(data, key=lambda x: x["count"], reverse=True)
    if len(sorted_data) > 8:
        top_data = sorted_data[:8]
        other_count = sum(d["count"] for d in sorted_data[8:])
        if other_count > 0:
            top_data.append({"country": "Other", "count": other_count})
        sorted_data = top_data

    labels = [d['country'] or "Unknown" for d in sorted_data]
    values = [d["count"] for d in sorted_data]

    # Distinct colors for countries
    colors = [
        "#3b82f6",  # blue
        "#22c55e",  # green
        "#eab308",  # yellow
        "#a855f7",  # purple
        "#ef4444",  # red
        "#06b6d4",  # cyan
        "#f97316",  # orange
        "#ec4899",  # pink
        "#6b7280",  # gray (for "Other")
    ]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.4,
                marker_colors=colors[:len(labels)],
                textinfo="none",  # Hide text on chart, show only on hover
                hovertemplate="<b>%{label}</b><br>%{value} accounts<br>%{percent}<extra></extra>",
            )
        ]
    )

    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.02,
            font=dict(color="white", size=11),
            bgcolor="rgba(0,0,0,0)",
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=100, t=10, b=10),
        height=280,
    )

    ui.plotly(fig).classes("w-full")


def activity_line_chart(data: List[Dict[str, Any]]):
    """
    Create a line chart showing activity over time.

    Args:
        data: List of dicts with 'day' and 'count' keys
    """
    if not data:
        ui.label("Нет данных").classes("text-slate-400")
        return

    days = [d["day"] for d in data]
    counts = [d["count"] for d in data]

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=days,
            y=counts,
            mode="lines+markers",
            name="Действия",
            line=dict(color="#3b82f6", width=3),
            marker=dict(size=8, color="#3b82f6"),
            fill="tozeroy",
            fillcolor="rgba(59, 130, 246, 0.2)",
        )
    )

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=30, b=40),
        height=300,
        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(148, 163, 184, 0.1)",
            tickfont=dict(color="#94a3b8"),
            tickangle=-45,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(148, 163, 184, 0.1)",
            tickfont=dict(color="#94a3b8"),
        ),
        hovermode="x unified",
    )

    ui.plotly(fig).classes("w-full")


def bar_chart(
    labels: List[str],
    values: List[int],
    title: str = "",
    color: str = "#3b82f6",
    horizontal: bool = False
):
    """
    Create a bar chart.

    Args:
        labels: X-axis labels
        values: Bar values
        title: Chart title
        color: Bar color
        horizontal: If True, create horizontal bar chart
    """
    if not labels or not values:
        ui.label("Нет данных").classes("text-slate-400")
        return

    if horizontal:
        fig = go.Figure(
            data=[
                go.Bar(
                    y=labels,
                    x=values,
                    orientation="h",
                    marker_color=color,
                )
            ]
        )
    else:
        fig = go.Figure(
            data=[
                go.Bar(
                    x=labels,
                    y=values,
                    marker_color=color,
                )
            ]
        )

    fig.update_layout(
        title=dict(text=title, font=dict(color="white")) if title else None,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=40 if title else 20, b=40),
        height=300,
        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(148, 163, 184, 0.1)",
            tickfont=dict(color="#94a3b8"),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(148, 163, 184, 0.1)",
            tickfont=dict(color="#94a3b8"),
        ),
    )

    ui.plotly(fig).classes("w-full")


def multi_line_chart(
    x_data: List[str],
    series: List[Dict[str, Any]],
    title: str = ""
):
    """
    Create a multi-line chart.

    Args:
        x_data: X-axis values
        series: List of dicts with 'name', 'values', and optional 'color'
        title: Chart title
    """
    if not x_data or not series:
        ui.label("Нет данных").classes("text-slate-400")
        return

    fig = go.Figure()

    colors = ["#3b82f6", "#22c55e", "#eab308", "#a855f7", "#ef4444"]

    for i, s in enumerate(series):
        fig.add_trace(
            go.Scatter(
                x=x_data,
                y=s["values"],
                mode="lines+markers",
                name=s["name"],
                line=dict(color=s.get("color", colors[i % len(colors)]), width=2),
                marker=dict(size=6),
            )
        )

    fig.update_layout(
        title=dict(text=title, font=dict(color="white")) if title else None,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=40 if title else 20, b=40),
        height=300,
        legend=dict(
            font=dict(color="#94a3b8"),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(
            showgrid=True,
            gridcolor="rgba(148, 163, 184, 0.1)",
            tickfont=dict(color="#94a3b8"),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(148, 163, 184, 0.1)",
            tickfont=dict(color="#94a3b8"),
        ),
        hovermode="x unified",
    )

    ui.plotly(fig).classes("w-full")
