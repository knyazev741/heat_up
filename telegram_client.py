import httpx
import logging
from typing import Dict, Any, Optional
from config import settings
from telegram_tl_helpers import (
    make_get_dialogs_query,
    make_resolve_username_query,
)

logger = logging.getLogger(__name__)


class TelegramAPIClient:
    """Wrapper for Telegram session management API"""
    
    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = base_url or settings.telegram_api_base_url
        self.api_key = api_key or settings.telegram_api_key
        self.client = httpx.AsyncClient(timeout=30.0)
        
    async def close(self):
        await self.client.aclose()
        
    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    async def join_chat(self, session_id: str, chat_id: str) -> Dict[str, Any]:
        """
        Join a channel or chat
        
        Args:
            session_id: Telegram session UID
            chat_id: Channel username (e.g., @durov) or invite link
            
        Returns:
            API response
        """
        url = f"{self.base_url}/api/external/sessions/{session_id}/rpc/join_chat"
        payload = {
            "method": "join_chat",
            "params": {
                "chat_id": chat_id
            }
        }
        
        logger.info(f"Joining chat {chat_id} for session {session_id}")
        
        try:
            response = await self.client.post(
                url,
                json=payload,
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to join chat {chat_id}: {e.response.text}")
            return {"error": str(e), "status_code": e.response.status_code}
        except Exception as e:
            logger.error(f"Error joining chat {chat_id}: {str(e)}")
            return {"error": str(e)}
    
    async def send_message(
        self, 
        session_id: str, 
        chat_id: str, 
        text: str,
        disable_notification: bool = True
    ) -> Dict[str, Any]:
        """
        Send a message to a chat
        
        Args:
            session_id: Telegram session UID
            chat_id: Chat ID or username
            text: Message text
            disable_notification: Send silently
            
        Returns:
            API response
        """
        url = f"{self.base_url}/api/external/sessions/{session_id}/rpc/send_message"
        payload = {
            "method": "send_message",
            "params": {
                "chat_id": chat_id,
                "text": text,
                "disable_notification": disable_notification
            }
        }
        
        logger.info(f"Sending message to {chat_id} for session {session_id}")
        
        try:
            response = await self.client.post(
                url,
                json=payload,
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to send message: {e.response.text}")
            return {"error": str(e), "status_code": e.response.status_code}
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            return {"error": str(e)}
    
    async def invoke_raw(
        self, 
        session_id: str, 
        query: str,
        retries: int = 10,
        timeout: int = 15
    ) -> Dict[str, Any]:
        """
        Invoke raw Telegram RPC method
        
        Args:
            session_id: Telegram session UID
            query: Raw TL query (e.g., GetDialogsRequest)
            retries: Number of retries
            timeout: Request timeout
            
        Returns:
            API response
        """
        url = f"{self.base_url}/api/external/sessions/{session_id}/rpc/invoke"
        payload = {
            "method": "invoke",
            "params": {
                "query": query,
                "retries": retries,
                "timeout": timeout
            }
        }
        
        logger.info(f"Invoking raw query for session {session_id}")
        
        try:
            response = await self.client.post(
                url,
                json=payload,
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to invoke raw query: {e.response.text}")
            return {"error": str(e), "status_code": e.response.status_code}
        except Exception as e:
            logger.error(f"Error invoking raw query: {str(e)}")
            return {"error": str(e)}
    
    async def set_idle(self, session_id: str) -> Dict[str, Any]:
        """
        Set session to idle state
        
        Args:
            session_id: Telegram session UID
            
        Returns:
            API response
        """
        url = f"{self.base_url}/api/external/sessions/{session_id}/idle"
        
        logger.info(f"Setting session {session_id} to idle")
        
        try:
            response = await self.client.post(
                url,
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to set idle: {e.response.text}")
            return {"error": str(e), "status_code": e.response.status_code}
        except Exception as e:
            logger.error(f"Error setting idle: {str(e)}")
            return {"error": str(e)}
    
    async def get_dialogs(self, session_id: str, limit: int = 20) -> Dict[str, Any]:
        """
        Get user's dialogs (chats/channels) - simulates browsing
        
        Args:
            session_id: Telegram session UID
            limit: Number of dialogs to fetch
            
        Returns:
            API response
        """
        # Create proper TL query using pylogram
        query = make_get_dialogs_query(limit=limit)
        return await self.invoke_raw(session_id, query)

