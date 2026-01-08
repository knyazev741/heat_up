"""
RealChatEngine - Coordinator for participation in real public group chats.

This is the main engine for Phase 2 functionality:
1. Selects accounts eligible for real chat participation
2. Fetches and caches messages from joined groups
3. Analyzes context before responding
4. Generates and sends contextual responses

Safety features:
- Daily message limits per chat
- Context analysis before responding
- Minimum warmup stage requirements
- Natural timing between messages
"""

import asyncio
import random
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from telegram_client import TelegramAPIClient
from chat_context_analyzer import ChatContextAnalyzer
from admin_api_client import AdminAPIClient
from database import (
    get_accounts_eligible_for_real_chat_participation,
    get_chats_for_participation,
    get_cached_chat_messages,
    cache_real_chat_messages,
    can_send_message_in_chat,
    increment_chat_messages_sent,
    update_chat_participation,
    get_persona,
    get_account,
)

logger = logging.getLogger(__name__)

# Configuration
MIN_STAGE_FOR_REAL_CHAT = 8  # Minimum warmup stage for real chat participation
MIN_MESSAGES_FOR_CONTEXT = 5  # Minimum messages needed for context analysis
MAX_MESSAGES_PER_DAY_TOTAL = 10  # Max messages across all real chats per day
MIN_TIME_BETWEEN_MESSAGES = 300  # Minimum 5 minutes between messages
RESPONSE_CONFIDENCE_THRESHOLD = 0.6  # Minimum confidence to respond


class RealChatEngine:
    """
    Coordinates participation in real public group chats.

    This engine is responsible for:
    1. Finding accounts ready for real chat interaction
    2. Fetching messages from their joined groups
    3. Analyzing whether to respond
    4. Sending context-appropriate messages
    """

    def __init__(
        self,
        telegram_client: TelegramAPIClient,
        context_analyzer: ChatContextAnalyzer = None
    ):
        self.telegram = telegram_client
        self.analyzer = context_analyzer or ChatContextAnalyzer()

        # Track recent activity to prevent spam
        self._recent_messages: Dict[str, datetime] = {}  # session_id -> last_message_time

    async def process_real_chat_activity(self) -> Dict[str, Any]:
        """
        Main entry point - process real chat activity for eligible accounts.

        Called periodically by scheduler.

        Returns:
            Summary of activity
        """
        logger.info("🌐 Processing real chat activity...")

        summary = {
            "accounts_processed": 0,
            "messages_sent": 0,
            "chats_analyzed": 0,
            "errors": []
        }

        try:
            # Get eligible accounts
            accounts = get_accounts_eligible_for_real_chat_participation(
                min_stage=MIN_STAGE_FOR_REAL_CHAT,
                limit=20  # Fetch more, will filter by status
            )

            if not accounts:
                logger.info("No accounts eligible for real chat participation")
                return summary

            # Filter accounts by Admin API status=0
            # Only accounts with status=0 can write to real public chats
            admin_api = AdminAPIClient()
            eligible_accounts = []

            for account in accounts:
                session_id = account.get("session_id")
                try:
                    status = await admin_api.check_session_status(session_id)
                    if status == 0:
                        eligible_accounts.append(account)
                    else:
                        logger.debug(
                            f"Skipping account {session_id}: status={status} (need 0)"
                        )
                except Exception as e:
                    logger.warning(f"Could not check status for {session_id}: {e}")

            if not eligible_accounts:
                logger.info("No accounts with status=0 eligible for real chat")
                return summary

            accounts = eligible_accounts[:10]  # Limit to 10
            logger.info(
                f"Found {len(accounts)} accounts with status=0 eligible for real chat"
            )

            for account in accounts:
                try:
                    result = await self._process_account_activity(account)
                    summary["accounts_processed"] += 1
                    summary["messages_sent"] += result.get("messages_sent", 0)
                    summary["chats_analyzed"] += result.get("chats_analyzed", 0)
                except Exception as e:
                    logger.error(f"Error processing account {account.get('session_id')}: {e}")
                    summary["errors"].append(str(e))

                # Small delay between accounts
                await asyncio.sleep(random.uniform(2, 5))

        except Exception as e:
            logger.error(f"Error in real chat activity processing: {e}")
            summary["errors"].append(str(e))

        logger.info(f"Real chat activity complete: {summary}")
        return summary

    async def _process_account_activity(
        self,
        account: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process real chat activity for a single account.

        Args:
            account: Account dict with session_id, persona data, etc.

        Returns:
            Activity result
        """
        session_id = account.get("session_id")
        account_id = account.get("id")

        result = {
            "session_id": session_id,
            "messages_sent": 0,
            "chats_analyzed": 0
        }

        # Check recent activity - don't spam
        if self._recently_sent_message(session_id):
            logger.debug(f"Account {session_id} sent message recently, skipping")
            return result

        # Get persona data
        persona = get_persona(account_id)
        if not persona:
            persona = {
                "generated_name": account.get("generated_name", "User"),
                "interests": account.get("interests", []),
                "communication_style": account.get("communication_style", "friendly"),
                "personality_traits": account.get("personality_traits", []),
                "age": account.get("age", 25),
                "occupation": account.get("occupation", "")
            }

        # Get chats where we can participate
        chats = get_chats_for_participation(
            account_id=account_id,
            min_relevance=0.6,
            limit=3
        )

        if not chats:
            logger.debug(f"No eligible chats for account {session_id}")
            return result

        # Process each chat
        for chat in chats:
            try:
                chat_result = await self._process_chat_participation(
                    session_id=session_id,
                    account_id=account_id,
                    chat=chat,
                    persona=persona
                )

                result["chats_analyzed"] += 1

                if chat_result.get("message_sent"):
                    result["messages_sent"] += 1
                    self._record_message_sent(session_id)
                    break  # One message per cycle is enough

            except Exception as e:
                logger.error(f"Error processing chat {chat.get('chat_username')}: {e}")

            # Delay between chats
            await asyncio.sleep(random.uniform(1, 3))

        return result

    async def _process_chat_participation(
        self,
        session_id: str,
        account_id: int,
        chat: Dict[str, Any],
        persona: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process participation in a single chat.

        Steps:
        1. Check if we can send message (daily limit)
        2. Fetch recent messages
        3. Analyze context
        4. Send message if appropriate

        Args:
            session_id: Telegram session ID
            account_id: Account database ID
            chat: Chat info dict
            persona: Persona data dict

        Returns:
            Participation result
        """
        chat_username = chat.get("chat_username")
        result = {
            "chat_username": chat_username,
            "message_sent": False
        }

        # Check daily limit
        if not can_send_message_in_chat(account_id, chat_username):
            logger.debug(f"Daily limit reached for {chat_username}")
            return result

        # Fetch recent messages
        messages = await self._fetch_chat_messages(session_id, chat_username)

        if len(messages) < MIN_MESSAGES_FOR_CONTEXT:
            logger.debug(f"Not enough messages in {chat_username} for context")
            return result

        # Analyze context
        analysis = await self.analyzer.analyze_chat_context(
            messages=messages,
            persona=persona,
            chat_info={
                "title": chat.get("chat_title"),
                "type": chat.get("chat_type"),
                "member_count": chat.get("member_count")
            }
        )

        # Save analysis result
        update_chat_participation(
            account_id=account_id,
            chat_username=chat_username,
            last_analyzed_at=datetime.utcnow(),
            analysis_result=analysis
        )

        # Check if we should respond
        if not analysis.get("should_respond"):
            logger.info(f"Not responding in {chat_username}: {analysis.get('reason', 'unknown')}")
            return result

        if analysis.get("confidence", 0) < RESPONSE_CONFIDENCE_THRESHOLD:
            logger.info(f"Confidence too low ({analysis.get('confidence')}) for {chat_username}")
            return result

        # Get response text
        response_text = analysis.get("suggested_response")
        if not response_text:
            # Generate new response if not provided
            response_text = await self.analyzer.generate_contextual_response(
                messages=messages,
                persona=persona,
                target_message_id=analysis.get("target_message_id"),
                topic_hint=analysis.get("topic")
            )

        if not response_text:
            logger.warning(f"No response generated for {chat_username}")
            return result

        # Send the message
        send_result = await self._send_chat_message(
            session_id=session_id,
            chat_username=chat_username,
            text=response_text,
            reply_to_msg_id=analysis.get("target_message_id")
        )

        if send_result.get("success"):
            result["message_sent"] = True
            result["response_text"] = response_text[:50]

            # Update statistics
            increment_chat_messages_sent(account_id, chat_username)

            logger.info(f"✅ Sent message in {chat_username}: {response_text[:50]}...")

        return result

    async def _fetch_chat_messages(
        self,
        session_id: str,
        chat_username: str,
        limit: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent messages from a chat.

        First checks cache, then fetches from Telegram if needed.

        Args:
            session_id: Session to use for fetching
            chat_username: Chat to fetch from
            limit: Max messages to fetch

        Returns:
            List of message dicts
        """
        # Check cache first
        cached = get_cached_chat_messages(chat_username, limit=limit, max_age_hours=1)

        if len(cached) >= MIN_MESSAGES_FOR_CONTEXT:
            logger.debug(f"Using {len(cached)} cached messages for {chat_username}")
            return cached

        # Fetch from Telegram
        logger.debug(f"Fetching messages from {chat_username}")

        try:
            # Resolve peer first
            resolved = await self.telegram.resolve_peer(session_id, chat_username)
            if not resolved.get("success"):
                logger.warning(f"Could not resolve {chat_username}")
                return cached

            # Get history
            history = await self.telegram.get_chat_history(
                session_id=session_id,
                peer_info=resolved,
                limit=limit
            )

            if history.get("error"):
                logger.warning(f"Error fetching history from {chat_username}: {history.get('error')}")
                return cached

            # Parse messages
            messages = self._parse_messages(history.get("result", {}))

            if messages:
                # Cache for later
                cache_real_chat_messages(chat_username, messages)
                logger.debug(f"Cached {len(messages)} messages from {chat_username}")

            return messages or cached

        except Exception as e:
            logger.error(f"Error fetching messages from {chat_username}: {e}")
            return cached

    def _parse_messages(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse messages from Telegram API response"""
        messages = []

        raw_messages = result.get("messages", [])
        if isinstance(result, list):
            raw_messages = result

        users = {}
        for user in result.get("users", []):
            user_id = user.get("id")
            if user_id:
                name = user.get("first_name", "")
                if user.get("last_name"):
                    name += " " + user.get("last_name")
                users[user_id] = name or f"User{user_id}"

        for msg in raw_messages:
            if not isinstance(msg, dict):
                continue

            msg_id = msg.get("id")
            if not msg_id:
                continue

            text = msg.get("message") or msg.get("text") or ""
            from_id = msg.get("from_id", {})

            if isinstance(from_id, dict):
                sender_id = from_id.get("user_id")
            else:
                sender_id = from_id

            sender_name = users.get(sender_id, f"User{sender_id}" if sender_id else "Unknown")

            messages.append({
                "id": msg_id,
                "text": text,
                "sender_name": sender_name,
                "sender_id": sender_id,
                "date": msg.get("date"),
                "type": "text" if text else "media"
            })

        return messages

    async def _send_chat_message(
        self,
        session_id: str,
        chat_username: str,
        text: str,
        reply_to_msg_id: int = None
    ) -> Dict[str, Any]:
        """
        Send a message to a chat.

        Args:
            session_id: Session to send from
            chat_username: Chat to send to
            text: Message text
            reply_to_msg_id: Optional message ID to reply to

        Returns:
            Result dict with success status
        """
        try:
            # Use high-level send_message API
            result = await self.telegram.send_message(
                session_id=session_id,
                chat_id=chat_username,
                text=text,
                disable_notification=True
            )

            if result.get("error"):
                return {"success": False, "error": result.get("error")}

            return {"success": True, "message_id": result.get("message_id")}

        except Exception as e:
            logger.error(f"Error sending message to {chat_username}: {e}")
            return {"success": False, "error": str(e)}

    def _recently_sent_message(self, session_id: str) -> bool:
        """Check if account recently sent a message"""
        last_time = self._recent_messages.get(session_id)
        if not last_time:
            return False

        elapsed = (datetime.utcnow() - last_time).total_seconds()
        return elapsed < MIN_TIME_BETWEEN_MESSAGES

    def _record_message_sent(self, session_id: str):
        """Record that a message was sent"""
        self._recent_messages[session_id] = datetime.utcnow()

    async def analyze_chat_for_response(
        self,
        session_id: str,
        chat_username: str,
        persona: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Analyze a specific chat to determine if/how to respond.

        Can be called directly to check a specific chat.

        Args:
            session_id: Session ID to use
            chat_username: Chat to analyze
            persona: Optional persona data

        Returns:
            Analysis result
        """
        if not persona:
            account = get_account(session_id)
            if account:
                persona = get_persona(account.get("id"))

        messages = await self._fetch_chat_messages(session_id, chat_username)

        if not messages:
            return {
                "should_respond": False,
                "reason": "No messages found"
            }

        return await self.analyzer.analyze_chat_context(
            messages=messages,
            persona=persona or {}
        )

    async def participate_in_chat(
        self,
        session_id: str,
        chat_username: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Attempt to participate in a specific chat.

        Higher-level method that combines analysis and sending.

        Args:
            session_id: Session to use
            chat_username: Chat to participate in
            force: If True, send even if analysis says no

        Returns:
            Result with message_sent status
        """
        account = get_account(session_id)
        if not account:
            return {"error": "Account not found"}

        account_id = account.get("id")
        persona = get_persona(account_id) or {}

        chat = {
            "chat_username": chat_username,
            "chat_title": chat_username,
            "chat_type": "group"
        }

        return await self._process_chat_participation(
            session_id=session_id,
            account_id=account_id,
            chat=chat,
            persona=persona
        )
