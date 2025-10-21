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
        logger.debug(f"Query: {query[:200]}..." if len(query) > 200 else f"Query: {query}")
        
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
    
    async def send_reaction(
        self,
        session_id: str,
        chat_id: str,
        message_id: int,
        emoji: str = "👍"
    ) -> Dict[str, Any]:
        """
        Send a reaction to a message
        
        Args:
            session_id: Telegram session UID
            chat_id: Chat ID or username
            message_id: Message ID to react to
            emoji: Emoji reaction (default: 👍)
            
        Returns:
            API response
        """
        url = f"{self.base_url}/api/external/sessions/{session_id}/rpc/send_reaction"
        payload = {
            "method": "send_reaction",
            "params": {
                "chat_id": chat_id,
                "message_id": message_id,
                "emoji": emoji,
                "big": False
            }
        }
        
        logger.info(f"Sending reaction {emoji} to message {message_id} in {chat_id}")
        
        try:
            response = await self.client.post(
                url,
                json=payload,
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to send reaction: {e.response.text}")
            return {"error": str(e), "status_code": e.response.status_code}
        except Exception as e:
            logger.error(f"Error sending reaction: {str(e)}")
            return {"error": str(e)}
    
    async def get_channel_messages(
        self,
        session_id: str,
        chat_id: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get messages from a channel (for reading/reacting)
        
        Args:
            session_id: Telegram session UID
            chat_id: Channel ID or username
            limit: Number of messages to fetch
            
        Returns:
            API response with messages
        """
        url = f"{self.base_url}/api/external/sessions/{session_id}/rpc"
        payload = {
            "method": "get_chat_messages",
            "params": {
                "chat_id": chat_id,
                "limit": limit
            }
        }
        
        logger.info(f"Getting {limit} messages from {chat_id}")
        
        try:
            response = await self.client.post(
                url,
                json=payload,
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get messages: {e.response.text}")
            return {"error": str(e), "status_code": e.response.status_code}
        except Exception as e:
            logger.error(f"Error getting messages: {str(e)}")
            return {"error": str(e)}
    
    async def get_session_info(self, session_id: str) -> Dict[str, Any]:
        """
        Get session information including premium status
        
        Args:
            session_id: Telegram session UID
            
        Returns:
            Session data with is_premium and premium_end_date fields
        """
        url = f"{self.base_url}/api/external/sessions/{session_id}"
        
        logger.debug(f"Getting session info for {session_id}")
        
        try:
            response = await self.client.get(
                url,
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get session info: {e.response.text}")
            return {"error": str(e), "status_code": e.response.status_code}
        except Exception as e:
            logger.error(f"Error getting session info: {str(e)}")
            return {"error": str(e)}
    
    async def resolve_username(self, session_id: str, username: str) -> Dict[str, Any]:
        """
        Resolve username to check if it exists and get channel/user info
        
        Args:
            session_id: Telegram session UID
            username: Username to resolve (with or without @)
            
        Returns:
            API response with peer info or error
        """
        from telegram_tl_helpers import make_resolve_username_query
        
        username = username.lstrip('@')
        logger.debug(f"Resolving username @{username}")
        
        query = make_resolve_username_query(username)
        return await self.invoke_raw(session_id, query)
    
    async def resolve_chat(self, session_id: str, chat_username: str) -> Dict[str, Any]:
        """
        Resolve chat using high-level API (more reliable than low-level TL)
        
        Args:
            session_id: Telegram session UID  
            chat_username: Chat username (with or without @)
            
        Returns:
            API response with chat info or error
        """
        # Используем высокоуровневое API из OpenAPI (надежнее чем TL invoke)
        url = f"{self.base_url}/api/external/chats/resolve"
        payload = {
            "chat": chat_username,  # @ будет удален автоматически на сервере
            "session_id": int(session_id),
            "join_invite_link": False,  # НЕ вступать, только проверить
            "collect_extra_analytics": False,
            "timeout": 15,
            "max_attempts": 2
        }
        
        logger.info(f"🔍 Resolving chat {chat_username} using high-level API")
        
        try:
            response = await self.client.post(
                url,
                json=payload,
                headers=self._get_headers(),
                timeout=20.0
            )
            response.raise_for_status()
            result = response.json()
            
            # Проверяем результат
            if result.get("success"):
                logger.info(f"✅ Chat {chat_username} exists and is accessible")
                return {"success": True, "result": result}
            else:
                error = result.get("error", "Unknown error")
                error_code = result.get("error_code", "")
                logger.warning(f"⚠️ Chat {chat_username} resolve failed: {error} (code: {error_code})")
                return {"success": False, "error": error, "error_code": error_code}
                
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP error resolving {chat_username}: {e.response.text}")
            return {"success": False, "error": str(e), "status_code": e.response.status_code}
        except Exception as e:
            logger.error(f"❌ Error resolving {chat_username}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def get_sponsored_messages(
        self,
        session_id: str,
        channel_username: str
    ) -> Dict[str, Any]:
        """
        Get official sponsored messages (ads) for a channel
        
        According to Telegram's custom client guidelines, this MUST be called
        when opening channels/bots for non-premium users to display official ads.
        
        Args:
            session_id: Telegram session UID
            channel_username: Channel username (e.g., @SecretAdTestChannel)
            
        Returns:
            API response with sponsored messages or empty if premium/no ads
        """
        from telegram_tl_helpers import make_resolve_username_query, make_get_sponsored_messages_query, make_input_peer_channel
        
        # First, resolve username to get InputPeer
        resolve_query = make_resolve_username_query(channel_username)
        resolve_result = await self.invoke_raw(session_id, resolve_query)
        
        if resolve_result.get("error") or not resolve_result.get("success"):
            logger.warning(f"Failed to resolve {channel_username}: {resolve_result.get('error')}")
            return resolve_result
        
        # Extract peer info from resolved result
        result = resolve_result.get("result", {})
        peer = result.get("peer")
        chats = result.get("chats", [])
        
        if not peer or not chats:
            logger.warning(f"No peer/chats found for {channel_username}")
            return {"error": "Failed to resolve channel"}
        
        # Find the channel in chats to get channel_id and access_hash
        channel_id = None
        access_hash = None
        
        for chat in chats:
            chat_type = chat.get("_", "")
            # Check for both "Channel" and "types.Channel"
            if "Channel" in chat_type:
                channel_id = chat.get("id")
                access_hash = chat.get("access_hash")
                logger.debug(f"Found channel: id={channel_id}, access_hash={access_hash}")
                break
        
        if not channel_id or not access_hash:
            logger.warning(f"Could not extract channel_id/access_hash for {channel_username}")
            return {"error": "Failed to get channel info"}
        
        # Create InputPeerChannel
        input_peer_channel = make_input_peer_channel(channel_id, access_hash)
        
        # Get sponsored messages
        sponsored_query = make_get_sponsored_messages_query(input_peer_channel)
        
        logger.info(f"🎯 Requesting sponsored messages for {channel_username}")
        
        sponsored_result = await self.invoke_raw(session_id, sponsored_query)
        
        if sponsored_result.get("success"):
            logger.info(f"✅ Got sponsored messages response for {channel_username}")
        
        return sponsored_result
    
    async def view_sponsored_message(
        self,
        session_id: str,
        random_id: bytes
    ) -> Dict[str, Any]:
        """
        Mark sponsored message as viewed
        
        Should be called when the ad is fully visible on screen.
        
        Args:
            session_id: Telegram session UID
            random_id: Random ID from SponsoredMessage
            
        Returns:
            API response
        """
        from telegram_tl_helpers import make_view_sponsored_message_query
        
        query = make_view_sponsored_message_query(random_id)
        logger.debug(f"Marking sponsored message as viewed")
        
        return await self.invoke_raw(session_id, query)
    
    async def click_sponsored_message(
        self,
        session_id: str,
        random_id: bytes,
        media: bool = False,
        fullscreen: bool = False
    ) -> Dict[str, Any]:
        """
        Mark sponsored message as clicked
        
        Args:
            session_id: Telegram session UID
            random_id: Random ID from SponsoredMessage
            media: True if clicking on media
            fullscreen: True if video in fullscreen
            
        Returns:
            API response
        """
        from telegram_tl_helpers import make_click_sponsored_message_query
        
        query = make_click_sponsored_message_query(random_id, media, fullscreen)
        logger.debug(f"Marking sponsored message as clicked (media={media}, fullscreen={fullscreen})")
        
        return await self.invoke_raw(session_id, query)

