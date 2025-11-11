"""
Authentication module for API token validation
"""
import hashlib
import secrets
import json
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer()

# Path to tokens file
TOKENS_FILE = Path("data/api_tokens.json")


def generate_token() -> str:
    """Generate a secure random API token"""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash a token using SHA-256"""
    return hashlib.sha256(token.encode()).hexdigest()


def load_tokens() -> Dict[str, dict]:
    """
    Load tokens from file
    
    Returns:
        Dictionary with token_hash as key and token info as value
    """
    if not TOKENS_FILE.exists():
        logger.warning(f"Tokens file not found: {TOKENS_FILE}. Creating empty tokens store.")
        TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)
        save_tokens({})
        return {}
    
    try:
        with TOKENS_FILE.open('r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading tokens: {e}")
        return {}


def save_tokens(tokens: Dict[str, dict]):
    """Save tokens to file"""
    try:
        TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with TOKENS_FILE.open('w') as f:
            json.dump(tokens, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving tokens: {e}")
        raise


def create_token(name: str, description: str = "") -> str:
    """
    Create a new API token
    
    Args:
        name: Token name/identifier
        description: Optional description
        
    Returns:
        The generated token (plain text - show to user only once!)
    """
    tokens = load_tokens()
    
    # Generate token
    token = generate_token()
    token_hash = hash_token(token)
    
    # Check if token hash already exists (extremely unlikely but just in case)
    if token_hash in tokens:
        logger.warning("Token collision detected, regenerating...")
        return create_token(name, description)
    
    # Save token info
    tokens[token_hash] = {
        "name": name,
        "description": description,
        "created_at": datetime.utcnow().isoformat(),
        "last_used": None,
        "usage_count": 0
    }
    
    save_tokens(tokens)
    logger.info(f"Created new API token: {name}")
    
    return token


def validate_token(token: str) -> Optional[dict]:
    """
    Validate an API token
    
    Args:
        token: The token to validate
        
    Returns:
        Token info if valid, None otherwise
    """
    tokens = load_tokens()
    token_hash = hash_token(token)
    
    if token_hash not in tokens:
        return None
    
    # Update usage stats
    token_info = tokens[token_hash]
    token_info["last_used"] = datetime.utcnow().isoformat()
    token_info["usage_count"] = token_info.get("usage_count", 0) + 1
    save_tokens(tokens)
    
    return token_info


def revoke_token(token: str) -> bool:
    """
    Revoke an API token
    
    Args:
        token: The token to revoke (can be plain text or hash)
        
    Returns:
        True if revoked, False if not found
    """
    tokens = load_tokens()
    
    # Try as plain token first
    token_hash = hash_token(token)
    if token_hash in tokens:
        del tokens[token_hash]
        save_tokens(tokens)
        logger.info(f"Revoked token: {token_hash[:16]}...")
        return True
    
    # Try as hash
    if token in tokens:
        del tokens[token]
        save_tokens(tokens)
        logger.info(f"Revoked token: {token[:16]}...")
        return True
    
    return False


def list_tokens() -> List[dict]:
    """
    List all tokens (without showing the actual token)
    
    Returns:
        List of token info dictionaries
    """
    tokens = load_tokens()
    result = []
    
    for token_hash, info in tokens.items():
        result.append({
            "token_hash": token_hash[:16] + "...",  # Show only first 16 chars
            "name": info["name"],
            "description": info.get("description", ""),
            "created_at": info["created_at"],
            "last_used": info.get("last_used"),
            "usage_count": info.get("usage_count", 0)
        })
    
    return result


async def verify_api_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    """
    FastAPI dependency to verify API token
    
    Usage:
        @app.get("/protected")
        async def protected_route(token_info: dict = Depends(verify_api_token)):
            ...
    """
    token = credentials.credentials
    token_info = validate_token(token)
    
    if not token_info:
        logger.warning(f"Invalid API token attempt: {token[:16]}...")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired API token"
        )
    
    return token_info

