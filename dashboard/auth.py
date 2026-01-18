"""
Dashboard Authentication Module
Handles password verification and session management via cookies.
"""

import os
import hashlib
import secrets
from typing import Optional
from functools import wraps

import bcrypt
from nicegui import app, ui

# Default password hash for "admin" - should be changed in production
DEFAULT_PASSWORD_HASH = bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode()

def get_password_hash() -> str:
    """Get password hash from environment or use default."""
    return os.getenv("DASHBOARD_PASSWORD_HASH", DEFAULT_PASSWORD_HASH)

def get_secret_key() -> str:
    """Get secret key for cookie signing."""
    return os.getenv("DASHBOARD_SECRET", "heat_up_dashboard_secret_change_me")

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, password_hash: Optional[str] = None) -> bool:
    """Verify password against stored hash."""
    if password_hash is None:
        password_hash = get_password_hash()
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except Exception:
        return False

def generate_auth_token() -> str:
    """Generate a secure authentication token."""
    secret = get_secret_key()
    random_part = secrets.token_hex(32)
    combined = f"{secret}:{random_part}"
    return hashlib.sha256(combined.encode()).hexdigest()

def is_authenticated() -> bool:
    """Check if current user is authenticated."""
    auth_token = app.storage.user.get("auth_token")
    if not auth_token:
        return False
    # Validate token format (simple check)
    return len(auth_token) == 64 and auth_token.isalnum()

def login(password: str) -> bool:
    """Attempt to log in with password."""
    if verify_password(password):
        token = generate_auth_token()
        app.storage.user["auth_token"] = token
        return True
    return False

def logout():
    """Log out current user."""
    app.storage.user.pop("auth_token", None)

def require_auth(func):
    """Decorator to require authentication for a page."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        if not is_authenticated():
            ui.navigate.to("/login")
            return
        return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
    return wrapper

import asyncio
