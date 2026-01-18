"""
Connections page showing graph visualization of account relationships.
Uses pyvis for interactive network graph.
"""

from nicegui import ui
import tempfile
import os
from pathlib import Path

from dashboard.auth import is_authenticated
from dashboard.components.layout import page_layout, card
from dashboard.utils.queries import get_graph_nodes, get_graph_edges

# Try to import pyvis
try:
    from pyvis.network import Network
    PYVIS_AVAILABLE = True
except ImportError:
    PYVIS_AVAILABLE = False


def generate_graph_html(
    nodes: list,
    edges: list,
    filter_type: str = "all",
    filter_connection: str = "all",
    min_messages: int = 0,
    highlight_account: int = None
) -> str:
    """
    Generate HTML for the network graph.

    Args:
        nodes: List of node dicts
        edges: List of edge dicts
        filter_type: Account type filter (all, warmup, helper)
        filter_connection: Connection type filter (all, dm, group)
        min_messages: Minimum messages for edge
        highlight_account: Account ID to highlight

    Returns:
        HTML string for the graph
    """
    if not PYVIS_AVAILABLE:
        return "<div style='color: white; padding: 20px;'>pyvis not installed. Install with: pip install pyvis</div>"

    # Filter nodes by type
    if filter_type != "all":
        filtered_node_ids = {n["id"] for n in nodes if n.get("type") == filter_type}
        nodes = [n for n in nodes if n["id"] in filtered_node_ids]
    else:
        filtered_node_ids = {n["id"] for n in nodes}

    # Filter edges
    filtered_edges = []
    for edge in edges:
        # Type filter
        if filter_connection != "all" and edge.get("type") != filter_connection:
            continue
        # Min messages filter
        if edge.get("weight", 0) < min_messages:
            continue
        # Node existence filter
        if edge["from"] not in filtered_node_ids or edge["to"] not in filtered_node_ids:
            continue
        filtered_edges.append(edge)

    # If no nodes or no edges, show message
    if not nodes:
        return "<div style='color: #94a3b8; padding: 40px; text-align: center;'>No accounts found with current filters</div>"

    if not filtered_edges:
        return "<div style='color: #94a3b8; padding: 40px; text-align: center;'>No connections found with current filters.<br>DM connections and group memberships will appear here.</div>"

    # Create network
    net = Network(
        height="580px",
        width="100%",
        bgcolor="#0f172a",
        font_color="white",
        directed=False,
        select_menu=False,
        filter_menu=False,
        notebook=False
    )

    # Physics settings for better layout
    net.set_options("""
    {
        "physics": {
            "forceAtlas2Based": {
                "gravitationalConstant": -100,
                "centralGravity": 0.01,
                "springLength": 150,
                "springConstant": 0.08
            },
            "solver": "forceAtlas2Based",
            "stabilization": {
                "enabled": true,
                "iterations": 150,
                "updateInterval": 25
            }
        },
        "nodes": {
            "borderWidth": 2,
            "borderWidthSelected": 4,
            "font": {
                "size": 11,
                "face": "Arial"
            }
        },
        "edges": {
            "smooth": {
                "type": "continuous"
            },
            "color": {
                "inherit": false
            }
        },
        "interaction": {
            "hover": true,
            "tooltipDelay": 100,
            "zoomView": true,
            "dragView": true
        }
    }
    """)

    # Color mapping by stage
    def get_node_color(stage):
        if stage is None:
            return "#6b7280"  # gray
        elif stage <= 3:
            return "#22c55e"  # green
        elif stage <= 6:
            return "#eab308"  # yellow
        elif stage <= 9:
            return "#3b82f6"  # blue
        else:
            return "#a855f7"  # purple

    # Add nodes
    for node in nodes:
        node_id = node["id"]
        stage = node.get("stage", 1)
        color = get_node_color(stage)

        # Highlight selected node
        if highlight_account and node_id == highlight_account:
            border_color = "#ef4444"
            border_width = 4
        else:
            border_color = color
            border_width = 2

        # Node size based on actions
        actions = node.get("actions", 0)
        size = 15 + min(actions / 10, 20)

        # Plain text tooltip (HTML tags don't render in vis.js tooltips)
        title = f"""{node.get('name', f'Account {node_id}')}
Session: {node.get('session_id', 'N/A')[:12]}...
Stage: {stage}
Type: {node.get('type', 'warmup')}
Actions: {actions}
Click to open account"""

        net.add_node(
            node_id,
            label=node.get("name", f"#{node_id}")[:15],
            title=title,
            color={"background": color, "border": border_color},
            borderWidth=border_width,
            size=size,
            font={"color": "white"}
        )

    # Add edges
    for edge in filtered_edges:
        edge_color = "#3b82f6" if edge.get("type") == "dm" else "#22c55e"
        weight = edge.get("weight", 1)
        width = 1 + min(weight / 5, 5)

        title = f"DM: {weight} messages" if edge.get("type") == "dm" else "Shared group"

        net.add_edge(
            edge["from"],
            edge["to"],
            color=edge_color,
            width=width,
            title=title
        )

    # Generate HTML
    try:
        # Use temp file
        temp_dir = tempfile.mkdtemp()
        temp_file = os.path.join(temp_dir, "graph.html")
        net.save_graph(temp_file)

        with open(temp_file, "r", encoding="utf-8") as f:
            html = f.read()

        # Cleanup
        os.remove(temp_file)
        os.rmdir(temp_dir)

        # Inject double-click handler to navigate to account page via postMessage
        click_handler = """
        <script>
        network.on("doubleClick", function(params) {
            if (params.nodes.length > 0) {
                var nodeId = params.nodes[0];
                // Send message to parent window
                window.parent.postMessage({type: 'navigateToAccount', accountId: nodeId}, '*');
            }
        });
        </script>
        </body>
        """
        html = html.replace("</body>", click_handler)

        return html
    except Exception as e:
        return f"<div style='color: #ef4444; padding: 20px;'>Error generating graph: {e}</div>"


def create_connections_page():
    """Create the connections graph page."""

    # State
    state = {
        "filter_type": "all",
        "filter_connection": "all",
        "min_messages": 0,
        "search_account": "",
        "highlight_id": None
    }

    graph_container = None
    stats_container = None

    def render_graph():
        """Render the graph with current filters."""
        nonlocal graph_container

        nodes = get_graph_nodes()
        edges = get_graph_edges()

        # Parse search to find account ID
        highlight_id = None
        if state["search_account"]:
            search = state["search_account"].lower()
            for node in nodes:
                if (search in str(node["id"]) or
                    search in (node.get("name") or "").lower() or
                    search in (node.get("session_id") or "").lower()):
                    highlight_id = node["id"]
                    break

        html_content = generate_graph_html(
            nodes=nodes,
            edges=edges,
            filter_type=state["filter_type"],
            filter_connection=state["filter_connection"],
            min_messages=state["min_messages"],
            highlight_account=highlight_id
        )

        if graph_container:
            graph_container.clear()
            with graph_container:
                # Check if it's an error/info message (not full HTML)
                if html_content.startswith("<div"):
                    ui.html(html_content, sanitize=False).classes("w-full")
                else:
                    # Full pyvis HTML - use iframe with data URI
                    import base64
                    encoded = base64.b64encode(html_content.encode('utf-8')).decode('utf-8')
                    ui.html(f'''
                        <iframe
                            id="graph-iframe"
                            src="data:text/html;base64,{encoded}"
                            style="width: 100%; height: 580px; border: none; border-radius: 8px;"
                        ></iframe>
                    ''', sanitize=False).classes("w-full")
                    # Add message listener for double-click navigation
                    ui.run_javascript('''
                        if (!window._graphMessageListenerAdded) {
                            window._graphMessageListenerAdded = true;
                            window.addEventListener('message', function(event) {
                                if (event.data && event.data.type === 'navigateToAccount') {
                                    window.location.href = '/dashboard/accounts/' + event.data.accountId;
                                }
                            });
                        }
                    ''')

        # Update stats
        if stats_container:
            stats_container.clear()
            with stats_container:
                dm_edges = len([e for e in edges if e.get("type") == "dm"])
                group_edges = len([e for e in edges if e.get("type") == "group"])
                ui.label(f"Nodes: {len(nodes)}").classes("text-slate-400")
                ui.label(f"DM: {dm_edges}").classes("text-slate-400")
                ui.label(f"Groups: {group_edges}").classes("text-slate-400")

    def content():
        nonlocal graph_container, stats_container

        # Get accounts for quick navigation
        all_nodes = get_graph_nodes()
        account_options = {str(n["id"]): "{} (stage {})".format(n.get('name') or f'#{n["id"]}', n.get('stage', '?')) for n in all_nodes}

        # Filters row
        with ui.row().classes("w-full gap-4 items-end flex-wrap mb-4"):
            # Account type filter
            type_select = ui.select(
                {"all": "Все аккаунты", "warmup": "Warmup", "helper": "Helper"},
                value="all",
                label="Тип аккаунта"
            ).classes("w-40").props("dark outlined dense")
            type_select.on("update:model-value", lambda e: (
                state.update({"filter_type": e.value}),
                render_graph()
            ))

            # Connection type filter
            conn_select = ui.select(
                {"all": "Все связи", "dm": "Только DM", "group": "Только группы"},
                value="all",
                label="Тип связи"
            ).classes("w-40").props("dark outlined dense")
            conn_select.on("update:model-value", lambda e: (
                state.update({"filter_connection": e.value}),
                render_graph()
            ))

            # Min messages filter
            min_msg = ui.number(
                "Мин. сообщений",
                value=0,
                min=0,
                max=100
            ).classes("w-32").props("dark outlined dense")
            min_msg.on("update:model-value", lambda e: (
                state.update({"min_messages": int(e.value or 0)}),
                render_graph()
            ))

            # Search account
            search_input = ui.input(
                "Найти аккаунт",
                placeholder="ID, имя или session..."
            ).classes("w-48").props("dark outlined dense")
            search_input.on("keydown.enter", lambda: (
                state.update({"search_account": search_input.value}),
                render_graph()
            ))

            # Spacer
            ui.element("div").classes("flex-grow")

            # Quick navigate to account
            def go_to_account(e):
                if e.value:
                    ui.navigate.to(f"/dashboard/accounts/{e.value}")

            ui.select(
                account_options,
                label="Перейти к аккаунту",
                on_change=go_to_account
            ).classes("w-56").props("dark outlined dense")

            # Stats
            stats_container = ui.row().classes("items-center gap-4")

            # Refresh button
            ui.button("Обновить", icon="refresh", on_click=render_graph).props("flat")

        # Legend
        with ui.row().classes("w-full gap-6 mb-4"):
            with ui.row().classes("items-center gap-2"):
                ui.element("div").classes("w-4 h-4 rounded-full bg-green-500")
                ui.label("Stage 1-3").classes("text-slate-400 text-sm")

            with ui.row().classes("items-center gap-2"):
                ui.element("div").classes("w-4 h-4 rounded-full bg-yellow-500")
                ui.label("Stage 4-6").classes("text-slate-400 text-sm")

            with ui.row().classes("items-center gap-2"):
                ui.element("div").classes("w-4 h-4 rounded-full bg-blue-500")
                ui.label("Stage 7-9").classes("text-slate-400 text-sm")

            with ui.row().classes("items-center gap-2"):
                ui.element("div").classes("w-4 h-4 rounded-full bg-purple-500")
                ui.label("Stage 10+").classes("text-slate-400 text-sm")

            ui.label("|").classes("text-slate-600")

            with ui.row().classes("items-center gap-2"):
                ui.element("div").classes("w-8 h-1 bg-blue-500")
                ui.label("DM").classes("text-slate-400 text-sm")

            with ui.row().classes("items-center gap-2"):
                ui.element("div").classes("w-8 h-1 bg-green-500")
                ui.label("Группа").classes("text-slate-400 text-sm")

        # Graph container
        with card("").classes("w-full"):
            graph_container = ui.element("div").classes("w-full").style("height: 600px")

        # Initial render
        render_graph()

    def refresh():
        render_graph()
        ui.notify("Граф обновлён", type="positive")

    page_layout("Связи", content, refresh_callback=refresh)
