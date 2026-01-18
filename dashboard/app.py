#!/usr/bin/env python3
"""
Heat Up Dashboard - NiceGUI Application

Can be run standalone (python dashboard/app.py) on port 8081
OR integrated into FastAPI main.py via init_dashboard(app)
"""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nicegui import ui, app as nicegui_app
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import pages
from dashboard.pages.login import create_login_page
from dashboard.pages.overview import create_overview_page
from dashboard.pages.accounts import create_accounts_list_page, create_account_detail_page
from dashboard.pages.connections import create_connections_page
from dashboard.pages.channels import create_channels_page
from dashboard.pages.logs import create_logs_page
from dashboard.pages.settings import create_settings_page
from dashboard.auth import is_authenticated


def setup_routes():
    """Setup all dashboard routes (mount_path will add /dashboard prefix)."""

    @ui.page("/login")
    def login_page():
        """Login page."""
        create_login_page()

    @ui.page("/")
    def overview_page():
        """Main overview page."""
        if not is_authenticated():
            ui.navigate.to("/dashboard/login")
            return
        create_overview_page()

    @ui.page("/accounts")
    def accounts_list_page():
        """Accounts list page."""
        if not is_authenticated():
            ui.navigate.to("/dashboard/login")
            return
        create_accounts_list_page()

    @ui.page("/accounts/{account_id}")
    def account_detail_page(account_id: int):
        """Account detail page."""
        if not is_authenticated():
            ui.navigate.to("/dashboard/login")
            return
        create_account_detail_page(account_id)

    @ui.page("/connections")
    def connections_page():
        """Connections graph page."""
        if not is_authenticated():
            ui.navigate.to("/dashboard/login")
            return
        create_connections_page()

    @ui.page("/channels")
    def channels_page():
        """Channels and chats page."""
        if not is_authenticated():
            ui.navigate.to("/dashboard/login")
            return
        create_channels_page()

    @ui.page("/logs")
    def logs_page():
        """Global logs page."""
        if not is_authenticated():
            ui.navigate.to("/dashboard/login")
            return
        create_logs_page()

    @ui.page("/settings")
    def settings_page():
        """Settings page."""
        if not is_authenticated():
            ui.navigate.to("/dashboard/login")
            return
        create_settings_page()


def init_dashboard(fastapi_app, storage_secret: str = None):
    """
    Initialize dashboard and integrate with FastAPI app.

    Call this from main.py to mount dashboard at /dashboard/

    Args:
        fastapi_app: FastAPI application instance
        storage_secret: Secret for session storage (optional)

    Usage in main.py:
        from dashboard.app import init_dashboard
        init_dashboard(app)
    """
    # Set environment variable for base path (used by layout.py)
    os.environ["DASHBOARD_BASE_PATH"] = "/dashboard"

    # Configure storage secret
    secret = storage_secret or os.getenv("DASHBOARD_SECRET", "heat_up_dashboard_secret_key")
    nicegui_app.storage.secret = secret

    # Setup routes (will be prefixed with /dashboard by mount_path)
    setup_routes()

    # Mount NiceGUI into FastAPI at /dashboard
    ui.run_with(
        fastapi_app,
        title="Heat Up Dashboard",
        favicon="🔥",
        dark=True,
        storage_secret=secret,
        mount_path="/dashboard",
        reconnect_timeout=30.0,  # Longer timeout before showing disconnect message
    )

    print("Dashboard initialized at /dashboard/")


# ==================== Standalone Mode ====================

def setup_standalone_routes():
    """Setup routes for standalone mode (without /dashboard prefix)."""

    @ui.page("/login")
    def login_page():
        create_login_page()

    @ui.page("/")
    def overview_page():
        if not is_authenticated():
            ui.navigate.to("/login")
            return
        create_overview_page()

    @ui.page("/accounts")
    def accounts_list_page():
        if not is_authenticated():
            ui.navigate.to("/login")
            return
        create_accounts_list_page()

    @ui.page("/accounts/{account_id}")
    def account_detail_page(account_id: int):
        if not is_authenticated():
            ui.navigate.to("/login")
            return
        create_account_detail_page(account_id)

    @ui.page("/connections")
    def connections_page():
        if not is_authenticated():
            ui.navigate.to("/login")
            return
        create_connections_page()

    @ui.page("/channels")
    def channels_page():
        if not is_authenticated():
            ui.navigate.to("/login")
            return
        create_channels_page()

    @ui.page("/logs")
    def logs_page():
        if not is_authenticated():
            ui.navigate.to("/login")
            return
        create_logs_page()

    @ui.page("/settings")
    def settings_page():
        if not is_authenticated():
            ui.navigate.to("/login")
            return
        create_settings_page()


if __name__ in {"__main__", "__mp_main__"}:
    # Standalone mode - run on separate port (no prefix)
    os.environ["DASHBOARD_BASE_PATH"] = ""

    print("=" * 50)
    print("Heat Up Dashboard (Standalone Mode)")
    print("=" * 50)
    print("Starting on http://localhost:8081")
    print("Default password: admin")
    print("=" * 50)

    nicegui_app.storage.secret = os.getenv("DASHBOARD_SECRET", "heat_up_dashboard_secret_key")
    setup_standalone_routes()

    ui.run(
        host="0.0.0.0",
        port=8081,
        title="Heat Up Dashboard",
        favicon="🔥",
        dark=True,
        reload=False,
        show=False,
        storage_secret=nicegui_app.storage.secret,
        reconnect_timeout=30.0,  # Longer timeout before showing disconnect message
    )
