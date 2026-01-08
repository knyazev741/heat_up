"""
Admin API Client

This module provides a client for interacting with the KS Admin API
to fetch and manage session information.
"""

import httpx
import logging
from typing import Dict, Any, Optional, List
from config import settings

logger = logging.getLogger(__name__)


class AdminAPIClient:
    """Client for KS Admin API"""
    
    def __init__(self, base_url: str = None, api_key: str = None):
        """
        Initialize Admin API client
        
        Args:
            base_url: Admin API base URL (defaults to settings.admin_api_base_url)
            api_key: API key for authentication (defaults to settings.telegram_api_key)
        """
        self.base_url = base_url or settings.admin_api_base_url
        self.api_key = api_key or settings.telegram_api_key
        self.client = httpx.AsyncClient(timeout=30.0)
        
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
        
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers with authorization"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    async def get_sessions(
        self,
        skip: int = 0,
        limit: int = 100,
        frozen: Optional[bool] = None,
        deleted: Optional[bool] = None,
        spamblock: Optional[bool] = None,
        search: Optional[str] = None,
        status: Optional[int] = None,
        is_premium: Optional[bool] = None,
        country: Optional[str] = None,
        provider: Optional[str] = None,
        test_group: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get list of sessions with filtering and pagination
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return (max 100)
            frozen: Filter by frozen status
            deleted: Filter by deletion status
            spamblock: Filter by spam block status
            search: Search string for phone number, country or provider
            status: Filter by status
            is_premium: Filter by premium status
            country: Filter by country
            provider: Filter by provider
            test_group: Filter by test group
            
        Returns:
            Dict with 'items' (list of sessions) and 'total' (total count)
        """
        url = f"{self.base_url}/api/v1/sessions/"
        
        # Build query parameters
        params = {
            "skip": skip,
            "limit": min(limit, 100),  # Max 100 per API spec
        }
        
        # Add optional filters
        if frozen is not None:
            params["frozen"] = frozen
        if deleted is not None:
            params["deleted"] = deleted
        if spamblock is not None:
            params["spamblock"] = spamblock
        if search is not None:
            params["search"] = search
        if status is not None:
            params["status"] = status
        if is_premium is not None:
            params["is_premium"] = is_premium
        if country is not None:
            params["country"] = country
        if provider is not None:
            params["provider"] = provider
        if test_group is not None:
            params["test_group"] = test_group
        
        try:
            response = await self.client.get(
                url,
                headers=self._get_headers(),
                params=params
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting sessions: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error getting sessions: {e}")
            raise
    
    async def get_session_by_id(self, session_id: int) -> Dict[str, Any]:
        """
        Get session by ID
        
        Args:
            session_id: Session ID
            
        Returns:
            Session data
        """
        url = f"{self.base_url}/api/v1/sessions/{session_id}"
        
        try:
            response = await self.client.get(
                url,
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Session {session_id} not found in Admin API")
                return None
            logger.error(f"HTTP error getting session {session_id}: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error getting session {session_id}: {e}")
            raise
    
    async def get_session_by_phone(self, phone_number: str) -> Dict[str, Any]:
        """
        Get session by phone number
        
        Args:
            phone_number: Phone number
            
        Returns:
            Session data or None if not found
        """
        url = f"{self.base_url}/api/v1/sessions/by-phone/{phone_number}"
        
        try:
            response = await self.client.get(
                url,
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Session with phone {phone_number} not found in Admin API")
                return None
            logger.error(f"HTTP error getting session by phone {phone_number}: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error getting session by phone {phone_number}: {e}")
            raise
    
    async def get_frozen_sessions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all frozen sessions
        
        Args:
            limit: Maximum number of sessions per request (pagination handled internally)
            
        Returns:
            List of frozen session objects
        """
        all_sessions = []
        skip = 0
        
        while True:
            result = await self.get_sessions(
                skip=skip,
                limit=limit,
                frozen=True
            )
            
            items = result.get("items", [])
            all_sessions.extend(items)
            
            # Check if we've fetched all sessions
            if len(items) < limit:
                break
                
            skip += limit
        
        logger.info(f"Fetched {len(all_sessions)} frozen sessions from Admin API")
        return all_sessions
    
    async def get_deleted_sessions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all deleted sessions
        
        Args:
            limit: Maximum number of sessions per request (pagination handled internally)
            
        Returns:
            List of deleted session objects
        """
        all_sessions = []
        skip = 0
        
        while True:
            result = await self.get_sessions(
                skip=skip,
                limit=limit,
                deleted=True
            )
            
            items = result.get("items", [])
            all_sessions.extend(items)
            
            # Check if we've fetched all sessions
            if len(items) < limit:
                break
                
            skip += limit
        
        logger.info(f"Fetched {len(all_sessions)} deleted sessions from Admin API")
        return all_sessions
    
    async def get_session_by_session_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session by session_id string (telegram session UID)

        Args:
            session_id: Session UID string

        Returns:
            Session data or None if not found
        """
        # Use search to find by session_id
        try:
            result = await self.get_sessions(
                search=session_id,
                limit=1
            )

            items = result.get("items", [])
            if items:
                # Verify it's the exact match
                for item in items:
                    if str(item.get("session_id")) == str(session_id):
                        return item
                # Return first result if no exact match
                return items[0] if items else None

            return None
        except Exception as e:
            logger.error(f"Error getting session by session_id {session_id}: {e}")
            return None

    async def check_session_status(self, session_id: str) -> Optional[int]:
        """
        Check the status of a session in Admin API.

        Args:
            session_id: Session ID (which is the Admin API's `id` field)

        Returns:
            Status integer or None if not found
        """
        # Our session_id IS the Admin API's id, so use get_session_by_id
        try:
            session = await self.get_session_by_id(int(session_id))
            if session:
                return session.get("status")
        except (ValueError, TypeError):
            # session_id is not a valid integer, try search
            session = await self.get_session_by_session_id(session_id)
            if session:
                return session.get("status")
        return None

    async def get_banned_forever_sessions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all banned forever sessions (spamblock=true and no unban_date)

        Args:
            limit: Maximum number of sessions per request (pagination handled internally)

        Returns:
            List of banned forever session objects
        """
        all_sessions = []
        skip = 0

        while True:
            result = await self.get_sessions(
                skip=skip,
                limit=limit,
                spamblock=True
            )

            items = result.get("items", [])

            # Filter for only "forever banned" (no unban_date)
            forever_banned = [
                session for session in items
                if session.get("spamblock") and not session.get("unban_date")
            ]

            all_sessions.extend(forever_banned)

            # Check if we've fetched all sessions
            if len(items) < limit:
                break

            skip += limit

        logger.info(f"Fetched {len(all_sessions)} banned forever sessions from Admin API")
        return all_sessions

    async def get_helper_accounts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get helper accounts (spamblock=true, status=2, not deleted/frozen).

        Helper accounts:
        - Have permanent spamblock (can't initiate DMs)
        - CAN respond to DMs
        - CAN write in groups
        - Used as "crowd" for conversations between warmup bots

        Args:
            limit: Maximum number of sessions per request (pagination handled internally)

        Returns:
            List of helper session objects with session_id, phone, first_name, last_name
        """
        all_sessions = []
        skip = 0

        while True:
            result = await self.get_sessions(
                skip=skip,
                limit=limit,
                spamblock=True,
                status=2,  # Active status
                frozen=False,
                deleted=False
            )

            items = result.get("items", [])
            all_sessions.extend(items)

            # Check if we've fetched all sessions
            if len(items) < limit:
                break

            skip += limit

        logger.info(f"Fetched {len(all_sessions)} helper accounts from Admin API")
        return all_sessions


# Singleton instance
_admin_api_client: Optional[AdminAPIClient] = None


def get_admin_api_client() -> AdminAPIClient:
    """Get singleton instance of AdminAPIClient"""
    global _admin_api_client
    if _admin_api_client is None:
        _admin_api_client = AdminAPIClient()
    return _admin_api_client


async def close_admin_api_client():
    """Close singleton AdminAPIClient"""
    global _admin_api_client
    if _admin_api_client is not None:
        await _admin_api_client.close()
        _admin_api_client = None

