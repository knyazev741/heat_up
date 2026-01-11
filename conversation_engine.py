"""
Conversation Engine

Coordinates private conversations between bot accounts.
Handles conversation lifecycle, message timing, and Admin API status checks.
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from database import (
    get_account, get_account_by_id, get_persona,
    create_conversation, get_conversation, get_active_conversation,
    get_conversations_needing_response, update_conversation,
    save_conversation_message, get_conversation_messages,
    get_last_conversation_message, get_accounts_without_active_conversations,
    get_potential_conversation_partners, count_active_conversations,
    MIN_STAGE_FOR_DM
)
from conversation_agent import get_conversation_agent
from telegram_client import TelegramAPIClient
from admin_api_client import get_admin_api_client

logger = logging.getLogger(__name__)


class ConversationEngine:
    """
    Coordinates private conversations between bot accounts.

    Responsibilities:
    - Start new conversations (warmup -> any account)
    - Process pending responses
    - Check Admin API for status=1 restriction
    - Handle natural conversation endings
    """

    def __init__(self, telegram_client: TelegramAPIClient = None):
        self.telegram = telegram_client or TelegramAPIClient()
        self.agent = get_conversation_agent()
        self.admin_api = get_admin_api_client()

        # Configuration
        self.max_active_conversations = 50  # Total limit
        self.max_conversations_per_account = 3  # Per account limit
        self.min_response_delay_seconds = 30  # Minimum delay between messages
        self.max_response_delay_seconds = 600  # Maximum delay (10 minutes)
        self.max_messages_per_conversation = 30  # End conversation after this
        self.max_conversation_age_hours = 48  # End conversation after this

    async def can_initiate_dm_to_session(
        self,
        target_session_id: str,
        initiator_session_id: str
    ) -> tuple[bool, str]:
        """
        Check if we can start a new DM to target session.

        Rules:
        1. If there's already an active conversation - still check BOTH statuses
        2. If initiator has status != 0 in Admin API - CANNOT send DM
        3. If target has status != 0 in Admin API - CANNOT receive DM
        4. If target is deleted/frozen/banned forever - CANNOT
        5. Otherwise - OK

        Args:
            target_session_id: Session ID to check
            initiator_session_id: Session ID of the initiator

        Returns:
            Tuple of (can_initiate, reason)
        """
        # 1. Check INITIATOR status first (must be status=0 to send DMs)
        try:
            initiator_status = await self.admin_api.check_session_status(initiator_session_id)
            if initiator_status != 0:
                logger.info(
                    f"Cannot initiate DM from {initiator_session_id}: status={initiator_status} (need 0)"
                )
                return False, f"initiator_status_{initiator_status}_cannot_send_dm"
        except Exception as e:
            logger.warning(f"Admin API check failed for initiator {initiator_session_id}: {e}")
            return False, "initiator_status_check_failed"

        # 2. Check our local database for target
        target_account = get_account(target_session_id)
        if not target_account:
            return False, "target_not_in_database"

        if target_account.get("is_deleted"):
            return False, "target_is_deleted"

        if target_account.get("is_frozen"):
            return False, "target_is_frozen"

        if target_account.get("is_banned") and not target_account.get("unban_date"):
            return False, "target_banned_forever"

        # 3. Check TARGET status in Admin API (must be status=0 to receive DMs)
        try:
            target_status = await self.admin_api.check_session_status(target_session_id)
            if target_status != 0:
                logger.info(
                    f"Cannot initiate DM to {target_session_id}: status={target_status} (need 0)"
                )
                return False, f"target_status_{target_status}_cannot_receive_dm"
        except Exception as e:
            logger.warning(f"Admin API check failed for target {target_session_id}: {e}")
            return False, "target_status_check_failed"

        return True, "ok"

    async def start_new_conversation(
        self,
        initiator_session_id: str,
        target_session_id: str,
        common_context: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Start a new private conversation between two accounts.

        Args:
            initiator_session_id: Session ID of the one starting the conversation
            target_session_id: Session ID of the conversation partner
            common_context: Optional context for how they met

        Returns:
            Conversation dict or None if failed
        """
        # 1. Check if we can initiate
        can_initiate, reason = await self.can_initiate_dm_to_session(
            target_session_id, initiator_session_id
        )

        if not can_initiate:
            logger.warning(
                f"Cannot start conversation {initiator_session_id[:8]} -> "
                f"{target_session_id[:8]}: {reason}"
            )
            return None

        # 2. Get accounts and personas
        initiator_account = get_account(initiator_session_id)
        target_account = get_account(target_session_id)

        if not initiator_account or not target_account:
            logger.error("Cannot find accounts for conversation")
            return None

        # Check warmup stage
        if initiator_account.get("warmup_stage", 0) < MIN_STAGE_FOR_DM:
            logger.warning(
                f"Initiator {initiator_session_id[:8]} has low warmup stage "
                f"({initiator_account.get('warmup_stage')}), need >= {MIN_STAGE_FOR_DM}"
            )
            return None

        initiator_persona = get_persona(initiator_account["id"]) or {}
        target_persona = get_persona(target_account["id"]) or {}

        # 3. Generate starter message
        starter_message = await self.agent.generate_conversation_starter(
            my_persona=initiator_persona,
            their_persona=target_persona,
            common_context=common_context
        )

        if not starter_message:
            logger.error("Failed to generate conversation starter")
            return None

        # 4. Send message via Telegram
        # First, get target's ACTUAL phone from Telegram API (local DB may be stale)
        target_phone = await self.telegram.get_own_phone_number(target_session_id)
        if not target_phone:
            logger.error(f"Could not get real phone for target {target_session_id[:8]}")
            return None

        logger.info(f"Target's real phone: {target_phone}")

        # Import contact to get user_id and access_hash
        import_result = await self.telegram.import_contact(
            session_id=initiator_session_id,
            phone=target_phone,
            first_name=target_persona.get("generated_name", "Contact").split()[0] if target_persona.get("generated_name") else "Contact",
            last_name=""
        )

        if not import_result.get("success"):
            logger.error(
                f"Failed to import contact {target_phone}: {import_result.get('error')}"
            )
            return None

        target_user_id = import_result.get("user_id")
        target_access_hash = import_result.get("access_hash")

        if not target_user_id or target_access_hash is None:
            logger.error(f"No user_id/access_hash for {target_phone}")
            return None

        # Send DM using raw TL method with access_hash
        send_result = await self.telegram.send_dm_to_user(
            session_id=initiator_session_id,
            user_id=target_user_id,
            access_hash=target_access_hash,
            message=starter_message
        )

        if send_result.get("error"):
            logger.error(f"Failed to send starter message: {send_result.get('error')}")
            return None

        # 5. Create conversation in database
        conversation_id = create_conversation(
            initiator_account_id=initiator_account["id"],
            responder_account_id=target_account["id"],
            initiator_session_id=initiator_session_id,
            responder_session_id=target_session_id,
            conversation_starter=starter_message,
            common_context=common_context
        )

        if not conversation_id:
            logger.error("Failed to create conversation in database")
            return None

        # 6. Save the first message
        save_conversation_message(
            conversation_id=conversation_id,
            sender_account_id=initiator_account["id"],
            message_text=starter_message,
            telegram_message_id=send_result.get("message_id")
        )

        # 7. Schedule response from target
        response_delay = random.uniform(
            self.min_response_delay_seconds,
            self.max_response_delay_seconds
        )
        next_response = datetime.utcnow() + timedelta(seconds=response_delay)

        update_conversation(
            conversation_id,
            message_count=1,
            initiator_messages=1,
            next_response_after=next_response
        )

        logger.info(
            f"Started conversation {conversation_id}: "
            f"{initiator_session_id[:8]} -> {target_session_id[:8]}, "
            f"next response in {response_delay:.0f}s"
        )

        return get_conversation(conversation_id)

    async def process_pending_responses(self) -> int:
        """
        Process all conversations that need a response.

        Returns:
            Number of responses sent
        """
        pending = get_conversations_needing_response()
        responses_sent = 0

        for conversation in pending:
            try:
                success = await self._process_conversation(conversation)
                if success:
                    responses_sent += 1
            except Exception as e:
                logger.error(
                    f"Error processing conversation {conversation.get('id')}: {e}"
                )

        if responses_sent > 0:
            logger.info(f"Processed {responses_sent} conversation responses")

        return responses_sent

    async def _process_conversation(self, conversation: Dict[str, Any]) -> bool:
        """
        Process a single conversation - send the next response.

        Args:
            conversation: Conversation dict from database

        Returns:
            True if response was sent successfully
        """
        conversation_id = conversation["id"]

        # 1. Determine who should respond
        last_message = get_last_conversation_message(conversation_id)
        if not last_message:
            logger.warning(f"No messages in conversation {conversation_id}")
            return False

        # Responder is the one who didn't send the last message
        if last_message["sender_account_id"] == conversation["initiator_account_id"]:
            responder_account_id = conversation["responder_account_id"]
            responder_session_id = conversation["responder_session_id"]
            peer_account_id = conversation["initiator_account_id"]
        else:
            responder_account_id = conversation["initiator_account_id"]
            responder_session_id = conversation["initiator_session_id"]
            peer_account_id = conversation["responder_account_id"]

        # Get peer's account for sending DM
        peer_account = get_account_by_id(peer_account_id)
        if not peer_account:
            logger.error(f"Peer account {peer_account_id} not found")
            return False

        # Get peer's session_id to fetch real phone from Telegram
        peer_session_id = peer_account.get("session_id")
        if not peer_session_id:
            logger.error(f"Peer account has no session_id")
            return False

        # 2. Check Admin API status for BOTH participants before continuing
        try:
            responder_status = await self.admin_api.check_session_status(responder_session_id)
            if responder_status != 0:
                logger.warning(
                    f"Conversation {conversation_id}: responder {responder_session_id} has status={responder_status}, "
                    f"ending conversation (only status=0 can participate in DMs)"
                )
                update_conversation(
                    conversation_id,
                    status="ended",
                    end_reason=f"responder_status_{responder_status}",
                    next_response_after=None
                )
                return False
        except Exception as e:
            logger.warning(f"Failed to check responder status: {e}, ending conversation for safety")
            update_conversation(
                conversation_id,
                status="ended",
                end_reason="status_check_failed",
                next_response_after=None
            )
            return False

        try:
            peer_status = await self.admin_api.check_session_status(peer_session_id)
            if peer_status != 0:
                logger.warning(
                    f"Conversation {conversation_id}: peer {peer_session_id} has status={peer_status}, "
                    f"ending conversation (only status=0 can participate in DMs)"
                )
                update_conversation(
                    conversation_id,
                    status="ended",
                    end_reason=f"peer_status_{peer_status}",
                    next_response_after=None
                )
                return False
        except Exception as e:
            logger.warning(f"Failed to check peer status: {e}, ending conversation for safety")
            update_conversation(
                conversation_id,
                status="ended",
                end_reason="status_check_failed",
                next_response_after=None
            )
            return False

        # Fetch actual phone from Telegram API (local DB may be stale)
        peer_phone = await self.telegram.get_own_phone_number(peer_session_id)
        if not peer_phone:
            logger.error(f"Could not get real phone for peer {peer_session_id[:8]}")
            return False

        # 3. Check if conversation should end
        if await self._should_end_conversation(conversation):
            await self._end_conversation(conversation, responder_session_id)
            return True

        # 3. Get personas
        responder_persona = get_persona(responder_account_id) or {}

        other_account_id = (
            conversation["initiator_account_id"]
            if responder_account_id == conversation["responder_account_id"]
            else conversation["responder_account_id"]
        )
        other_persona = get_persona(other_account_id) or {}

        # 4. Get conversation history
        messages = get_conversation_messages(conversation_id, limit=20)

        # Mark which messages are from the responder
        for msg in messages:
            msg["is_mine"] = msg["sender_account_id"] == responder_account_id

        # 5. Generate response
        response_text = await self.agent.generate_conversation_response(
            my_persona=responder_persona,
            their_persona=other_persona,
            conversation_history=messages,
            current_topic=conversation.get("current_topic")
        )

        if not response_text:
            logger.warning(f"Failed to generate response for conversation {conversation_id}")
            # Reschedule for later
            next_try = datetime.utcnow() + timedelta(minutes=5)
            update_conversation(conversation_id, next_response_after=next_try)
            return False

        # 6. Send the response
        # Import peer as contact to get access_hash
        peer_persona = get_persona(peer_account_id) or {}
        import_result = await self.telegram.import_contact(
            session_id=responder_session_id,
            phone=peer_phone,
            first_name=peer_persona.get("generated_name", "Contact").split()[0] if peer_persona.get("generated_name") else "Contact",
            last_name=""
        )

        if not import_result.get("success"):
            logger.error(f"Failed to import contact for response: {import_result.get('error')}")
            next_try = datetime.utcnow() + timedelta(minutes=10)
            update_conversation(conversation_id, next_response_after=next_try)
            return False

        peer_user_id = import_result.get("user_id")
        peer_access_hash = import_result.get("access_hash")

        if not peer_user_id or peer_access_hash is None:
            logger.error(f"No user_id/access_hash for peer")
            return False

        send_result = await self.telegram.send_dm_to_user(
            session_id=responder_session_id,
            user_id=peer_user_id,
            access_hash=peer_access_hash,
            message=response_text
        )

        if send_result.get("error"):
            logger.error(
                f"Failed to send response in conversation {conversation_id}: "
                f"{send_result.get('error')}"
            )
            # Reschedule
            next_try = datetime.utcnow() + timedelta(minutes=10)
            update_conversation(conversation_id, next_response_after=next_try)
            return False

        # 7. Save message
        save_conversation_message(
            conversation_id=conversation_id,
            sender_account_id=responder_account_id,
            message_text=response_text,
            telegram_message_id=send_result.get("message_id")
        )

        # 8. Update conversation stats
        new_message_count = conversation.get("message_count", 0) + 1

        # Update initiator/responder message counts
        if responder_account_id == conversation["initiator_account_id"]:
            initiator_msgs = conversation.get("initiator_messages", 0) + 1
            responder_msgs = conversation.get("responder_messages", 0)
        else:
            initiator_msgs = conversation.get("initiator_messages", 0)
            responder_msgs = conversation.get("responder_messages", 0) + 1

        # Calculate next response delay
        next_delay = self._calculate_next_response_delay(new_message_count)
        next_response = datetime.utcnow() + timedelta(seconds=next_delay)

        update_conversation(
            conversation_id,
            message_count=new_message_count,
            initiator_messages=initiator_msgs,
            responder_messages=responder_msgs,
            last_message_at=datetime.utcnow(),
            next_response_after=next_response
        )

        logger.info(
            f"Sent response in conversation {conversation_id} "
            f"({new_message_count} total), next in {next_delay:.0f}s"
        )

        return True

    def _calculate_next_response_delay(self, message_count: int) -> float:
        """
        Calculate delay until next response.

        Longer conversations have longer pauses.

        Args:
            message_count: Number of messages so far

        Returns:
            Delay in seconds
        """
        base_delay = random.uniform(
            self.min_response_delay_seconds,
            self.max_response_delay_seconds
        )

        # Scale up for longer conversations
        if message_count > 10:
            base_delay *= 1.5
        if message_count > 20:
            base_delay *= 1.5

        # Sometimes add a longer pause (person is busy)
        if random.random() < 0.1:  # 10% chance
            base_delay += random.uniform(600, 1800)  # +10-30 minutes

        return base_delay

    async def _get_telegram_id(self, session_id: str) -> Optional[int]:
        """
        Get telegram_id for a session from Admin API.

        Args:
            session_id: Session ID string

        Returns:
            telegram_id integer or None if not found
        """
        try:
            session = await self.admin_api.get_session_by_session_id(session_id)
            if session:
                return session.get("telegram_id")
            return None
        except Exception as e:
            logger.error(f"Failed to get telegram_id for {session_id[:8]}: {e}")
            return None

    async def _should_end_conversation(self, conversation: Dict[str, Any]) -> bool:
        """
        Determine if conversation should end.

        Reasons:
        - Too many messages
        - Too old
        - Random chance (natural ending)

        Args:
            conversation: Conversation dict

        Returns:
            True if should end
        """
        message_count = conversation.get("message_count", 0)

        # Hard limit on messages
        if message_count >= self.max_messages_per_conversation:
            return True

        # Age limit
        started_at_str = conversation.get("started_at")
        if started_at_str:
            try:
                started_at = datetime.fromisoformat(str(started_at_str))
                age_hours = (datetime.utcnow() - started_at).total_seconds() / 3600

                if age_hours > self.max_conversation_age_hours:
                    return True
            except:
                pass

        # Probabilistic ending after 15 messages
        if message_count > 15 and random.random() < 0.15:  # 15% chance per message
            return True

        return False

    async def _end_conversation(
        self,
        conversation: Dict[str, Any],
        responder_session_id: str
    ):
        """
        End a conversation naturally.

        Args:
            conversation: Conversation dict
            responder_session_id: Session ID of who should send closing
        """
        conversation_id = conversation["id"]

        # Get persona for closing message
        responder_account = get_account(responder_session_id)
        if responder_account:
            responder_persona = get_persona(responder_account["id"]) or {}
        else:
            responder_persona = {}

        # Get recent messages for context
        messages = get_conversation_messages(conversation_id, limit=5)

        # Generate closing
        closing_text = await self.agent.generate_closing_message(
            my_persona=responder_persona,
            recent_messages=messages
        )

        # Determine peer first
        if responder_session_id == conversation["initiator_session_id"]:
            peer_account_id = conversation["responder_account_id"]
            peer_session_id = conversation["responder_session_id"]
        else:
            peer_account_id = conversation["initiator_account_id"]
            peer_session_id = conversation["initiator_session_id"]

        # Check BOTH statuses before sending closing message
        can_send_closing = closing_text is not None
        if can_send_closing:
            try:
                responder_status = await self.admin_api.check_session_status(responder_session_id)
                if responder_status != 0:
                    logger.info(
                        f"Cannot send closing message: responder {responder_session_id} has status={responder_status}"
                    )
                    can_send_closing = False
            except Exception as e:
                logger.warning(f"Failed to check responder status for closing: {e}")
                can_send_closing = False

        if can_send_closing:
            try:
                peer_status = await self.admin_api.check_session_status(peer_session_id)
                if peer_status != 0:
                    logger.info(
                        f"Cannot send closing message: peer {peer_session_id} has status={peer_status}"
                    )
                    can_send_closing = False
            except Exception as e:
                logger.warning(f"Failed to check peer status for closing: {e}")
                can_send_closing = False

        if can_send_closing:
            # Get peer's actual phone from Telegram API
            peer_phone = await self.telegram.get_own_phone_number(peer_session_id)
            if peer_phone:
                peer_persona = get_persona(peer_account_id) or {}
                import_result = await self.telegram.import_contact(
                    session_id=responder_session_id,
                    phone=peer_phone,
                    first_name=peer_persona.get("generated_name", "Contact").split()[0] if peer_persona.get("generated_name") else "Contact",
                    last_name=""
                )

                if import_result.get("success"):
                    # Send closing message
                    await self.telegram.send_dm_to_user(
                        session_id=responder_session_id,
                        user_id=import_result.get("user_id"),
                        access_hash=import_result.get("access_hash"),
                        message=closing_text
                    )

                    # Save message only if sent
                    if responder_account:
                        save_conversation_message(
                            conversation_id=conversation_id,
                            sender_account_id=responder_account["id"],
                            message_text=closing_text
                        )

        # Mark conversation as ended
        update_conversation(
            conversation_id,
            status="ended",
            end_reason="natural",
            next_response_after=None
        )

        logger.info(f"Ended conversation {conversation_id} naturally")

    async def initiate_new_social_activities(self) -> int:
        """
        Find lonely accounts and start new conversations for them.

        Returns:
            Number of new conversations started
        """
        # Check if we have room for more conversations
        active_count = count_active_conversations()
        if active_count >= self.max_active_conversations:
            logger.debug(
                f"Max conversations reached ({active_count}/{self.max_active_conversations})"
            )
            return 0

        # Get accounts that need more conversations
        lonely_accounts = get_accounts_without_active_conversations(
            min_stage=MIN_STAGE_FOR_DM,
            max_active_conversations=self.max_conversations_per_account
        )

        if not lonely_accounts:
            return 0

        new_conversations = 0
        max_new_per_cycle = 3  # Don't create too many at once

        for account in lonely_accounts[:max_new_per_cycle]:
            # Find a conversation partner
            partners = get_potential_conversation_partners(
                initiator_session_id=account["session_id"],
                limit=5
            )

            if not partners:
                continue

            # Try to start conversation with first valid partner
            for partner in partners:
                can_dm, reason = await self.can_initiate_dm_to_session(
                    partner["session_id"],
                    account["session_id"]
                )

                if not can_dm:
                    continue

                # Start conversation
                result = await self.start_new_conversation(
                    initiator_session_id=account["session_id"],
                    target_session_id=partner["session_id"]
                )

                if result:
                    new_conversations += 1
                    break

            if new_conversations >= max_new_per_cycle:
                break

        if new_conversations > 0:
            logger.info(f"Started {new_conversations} new conversations")

        return new_conversations


# Singleton instance
_conversation_engine: Optional[ConversationEngine] = None


def get_conversation_engine(telegram_client: TelegramAPIClient = None) -> ConversationEngine:
    """Get singleton instance of ConversationEngine"""
    global _conversation_engine
    if _conversation_engine is None:
        _conversation_engine = ConversationEngine(telegram_client)
    return _conversation_engine
