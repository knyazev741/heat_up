"""
Group Engine

Coordinates private group activities between bot accounts.
Handles group creation, member management, and message generation.
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from database import (
    get_account, get_account_by_id, get_persona,
    create_bot_group, get_bot_group, get_active_bot_groups,
    get_bot_groups_needing_activity, update_bot_group,
    add_group_member, get_group_members, update_group_member,
    save_group_message, get_group_messages, get_last_group_message,
    count_active_bot_groups, get_accounts_without_group_membership,
    get_accounts_eligible_for_dm, MIN_STAGE_FOR_DM
)
from conversation_agent import get_conversation_agent
from telegram_client import TelegramAPIClient
from admin_api_client import get_admin_api_client

logger = logging.getLogger(__name__)


# Group topics for different types
GROUP_TOPICS = {
    "friends": [
        "Дружеский чат",
        "Общалка",
        "Болталка",
        "Наш чатик",
        "Тусовка"
    ],
    "thematic": [
        "Обсуждение фильмов",
        "Книжный клуб",
        "Путешествия",
        "Кулинария",
        "Спорт и фитнес",
        "Музыка",
        "Игры",
        "Технологии"
    ],
    "work": [
        "Рабочие вопросы",
        "Проектная группа",
        "Коллеги",
        "Офис"
    ]
}


class GroupEngine:
    """
    Coordinates private group activities between bot accounts.

    Responsibilities:
    - Create new private groups
    - Add members to groups
    - Generate group messages
    - Handle natural conversation flow in groups
    """

    def __init__(self, telegram_client: TelegramAPIClient = None):
        self.telegram = telegram_client or TelegramAPIClient()
        self.agent = get_conversation_agent()
        self.admin_api = get_admin_api_client()

        # Configuration
        self.max_active_groups = 20  # Total limit
        self.min_members_per_group = 3  # Minimum members
        self.max_members_per_group = 10  # Maximum members
        self.min_activity_interval_minutes = 30  # Minimum between messages
        self.max_activity_interval_minutes = 240  # Maximum between messages (4 hours)
        self.max_messages_per_group = 200  # Archive group after this
        self.max_group_age_days = 14  # Archive group after this

    async def create_new_group(
        self,
        creator_session_id: str,
        group_type: str = "friends",
        topic: str = None,
        initial_member_ids: List[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new private group with bot accounts.

        Args:
            creator_session_id: Session ID of the group creator
            group_type: Type of group (friends, thematic, work)
            topic: Optional topic for the group
            initial_member_ids: Session IDs of initial members to add

        Returns:
            Group dict or None if failed
        """
        # 1. Validate creator
        creator_account = get_account(creator_session_id)
        if not creator_account:
            logger.error(f"Creator account not found: {creator_session_id[:8]}")
            return None

        if creator_account.get("warmup_stage", 0) < MIN_STAGE_FOR_DM:
            logger.warning(
                f"Creator {creator_session_id[:8]} has low warmup stage "
                f"({creator_account.get('warmup_stage')}), need >= {MIN_STAGE_FOR_DM}"
            )
            return None

        # 2. Check group limit
        active_groups = count_active_bot_groups()
        if active_groups >= self.max_active_groups:
            logger.warning(
                f"Max groups reached ({active_groups}/{self.max_active_groups})"
            )
            return None

        # 3. Generate group title
        if not topic:
            topic = random.choice(GROUP_TOPICS.get(group_type, GROUP_TOPICS["friends"]))

        group_title = self._generate_group_title(topic, group_type)
        group_description = self._generate_group_description(topic, group_type)

        # 4. Create group via Telegram API
        create_result = await self.telegram.create_group(
            session_id=creator_session_id,
            title=group_title,
            users=[]  # Start with empty group, add members later
        )

        if create_result.get("error"):
            logger.error(f"Failed to create Telegram group: {create_result.get('error')}")
            return None

        telegram_chat_id = create_result.get("chat_id")
        telegram_invite_link = create_result.get("invite_link")

        if not telegram_chat_id:
            logger.error("No chat_id returned from Telegram group creation")
            return None

        # 5. Create group in database
        group_id = create_bot_group(
            telegram_chat_id=telegram_chat_id,
            telegram_invite_link=telegram_invite_link,
            group_title=group_title,
            group_description=group_description,
            group_type=group_type,
            topic=topic,
            creator_account_id=creator_account["id"],
            creator_session_id=creator_session_id
        )

        if not group_id:
            logger.error("Failed to create group in database")
            return None

        # 6. Add creator as admin member
        add_group_member(
            group_id=group_id,
            account_id=creator_account["id"],
            session_id=creator_session_id,
            role="admin"
        )

        # 7. Add initial members if provided
        if initial_member_ids:
            added_count = 0
            for member_session_id in initial_member_ids[:self.max_members_per_group - 1]:
                if member_session_id == creator_session_id:
                    continue

                success = await self._add_member_to_group(
                    group_id=group_id,
                    telegram_chat_id=telegram_chat_id,
                    telegram_invite_link=telegram_invite_link,
                    member_session_id=member_session_id,
                    inviter_session_id=creator_session_id
                )
                if success:
                    added_count += 1

            # Update member count
            update_bot_group(group_id, member_count=1 + added_count)

        # 8. Schedule first activity
        next_activity = datetime.utcnow() + timedelta(
            minutes=random.randint(5, 30)
        )
        update_bot_group(group_id, next_activity_after=next_activity)

        logger.info(
            f"Created group {group_id}: '{group_title}' ({group_type}), "
            f"creator={creator_session_id[:8]}"
        )

        return get_bot_group(group_id)

    async def _add_member_to_group(
        self,
        group_id: int,
        telegram_chat_id: int,
        telegram_invite_link: str,
        member_session_id: str,
        inviter_session_id: str
    ) -> bool:
        """
        Add a member to existing group.

        Args:
            group_id: Database group ID
            telegram_chat_id: Telegram chat ID
            telegram_invite_link: Telegram invite link
            member_session_id: Session ID of the member to add
            inviter_session_id: Session ID of who is inviting

        Returns:
            True if successfully added
        """
        member_account = get_account(member_session_id)
        if not member_account:
            logger.warning(f"Member account not found: {member_session_id[:8]}")
            return False

        # Check status via Admin API
        try:
            status = await self.admin_api.check_session_status(member_session_id)
            if status == 1:
                logger.info(f"Cannot add {member_session_id[:8]}: status=1")
                return False
        except Exception as e:
            logger.warning(f"Admin API check failed for {member_session_id[:8]}: {e}")

        # Join group via invite link
        if telegram_invite_link:
            join_result = await self.telegram.join_chat(
                session_id=member_session_id,
                chat_id=telegram_invite_link
            )

            if join_result.get("error"):
                logger.warning(
                    f"Failed to add {member_session_id[:8]} to group: "
                    f"{join_result.get('error')}"
                )
                return False

        # Add to database
        add_group_member(
            group_id=group_id,
            account_id=member_account["id"],
            session_id=member_session_id,
            role="member"
        )

        logger.info(f"Added member {member_session_id[:8]} to group {group_id}")
        return True

    async def add_members_to_group(
        self,
        group_id: int,
        member_session_ids: List[str]
    ) -> int:
        """
        Add multiple members to a group.

        Args:
            group_id: Database group ID
            member_session_ids: List of session IDs to add

        Returns:
            Number of members successfully added
        """
        group = get_bot_group(group_id)
        if not group:
            logger.error(f"Group {group_id} not found")
            return 0

        if group.get("status") != "active":
            logger.warning(f"Group {group_id} is not active")
            return 0

        current_members = group.get("member_count", 1)
        if current_members >= self.max_members_per_group:
            logger.warning(f"Group {group_id} is full ({current_members} members)")
            return 0

        telegram_chat_id = group.get("telegram_chat_id")
        telegram_invite_link = group.get("telegram_invite_link")
        creator_session_id = group.get("creator_session_id")

        added_count = 0
        max_to_add = self.max_members_per_group - current_members

        for member_session_id in member_session_ids[:max_to_add]:
            success = await self._add_member_to_group(
                group_id=group_id,
                telegram_chat_id=telegram_chat_id,
                telegram_invite_link=telegram_invite_link,
                member_session_id=member_session_id,
                inviter_session_id=creator_session_id
            )
            if success:
                added_count += 1

        if added_count > 0:
            update_bot_group(group_id, member_count=current_members + added_count)

        return added_count

    async def process_group_activities(self) -> int:
        """
        Process all groups that need activity.

        Returns:
            Number of messages sent
        """
        groups = get_bot_groups_needing_activity()
        messages_sent = 0

        for group in groups:
            try:
                # Check if group should be archived
                if await self._should_archive_group(group):
                    await self._archive_group(group)
                    continue

                success = await self._process_group_activity(group)
                if success:
                    messages_sent += 1
            except Exception as e:
                logger.error(
                    f"Error processing group {group.get('id')}: {e}"
                )

        if messages_sent > 0:
            logger.info(f"Processed {messages_sent} group activities")

        return messages_sent

    async def _process_group_activity(self, group: Dict[str, Any]) -> bool:
        """
        Process activity for a single group - send a message.

        Args:
            group: Group dict from database

        Returns:
            True if message was sent successfully
        """
        group_id = group["id"]
        telegram_chat_id = group.get("telegram_chat_id")

        if not telegram_chat_id:
            logger.error(f"Group {group_id} has no telegram_chat_id")
            return False

        # Get group members
        members = get_group_members(group_id)
        if len(members) < 2:
            logger.warning(f"Group {group_id} has too few members ({len(members)})")
            # Schedule next activity later, maybe more members will be added
            next_activity = datetime.utcnow() + timedelta(hours=2)
            update_bot_group(group_id, next_activity_after=next_activity)
            return False

        # Choose who should send the message
        sender = self._choose_message_sender(group, members)
        if not sender:
            logger.warning(f"No suitable sender for group {group_id}")
            return False

        sender_account_id = sender["account_id"]
        sender_session_id = sender["session_id"]
        sender_persona = get_persona(sender_account_id) or {}

        # Get other members' personas for context
        other_personas = []
        for member in members:
            if member["account_id"] != sender_account_id:
                persona = get_persona(member["account_id"])
                if persona:
                    other_personas.append(persona)

        # Get recent messages for context
        recent_messages = get_group_messages(group_id, limit=20)

        # Generate message
        message_text = await self._generate_group_message(
            group=group,
            sender_persona=sender_persona,
            other_personas=other_personas,
            recent_messages=recent_messages
        )

        if not message_text:
            logger.warning(f"Failed to generate message for group {group_id}")
            # Reschedule
            next_activity = datetime.utcnow() + timedelta(minutes=30)
            update_bot_group(group_id, next_activity_after=next_activity)
            return False

        # Send message via Telegram (use raw TL for groups)
        send_result = await self.telegram.send_message_to_group(
            session_id=sender_session_id,
            chat_id=telegram_chat_id,
            text=message_text,
            silent=True
        )

        if send_result.get("error"):
            logger.error(
                f"Failed to send group message: {send_result.get('error')}"
            )
            # Reschedule
            next_activity = datetime.utcnow() + timedelta(minutes=30)
            update_bot_group(group_id, next_activity_after=next_activity)
            return False

        # Save message to database
        save_group_message(
            group_id=group_id,
            sender_account_id=sender_account_id,
            message_text=message_text,
            telegram_message_id=send_result.get("message_id")
        )

        # Update group stats
        new_message_count = group.get("message_count", 0) + 1
        next_activity_delay = random.randint(
            self.min_activity_interval_minutes,
            self.max_activity_interval_minutes
        )
        next_activity = datetime.utcnow() + timedelta(minutes=next_activity_delay)

        update_bot_group(
            group_id,
            message_count=new_message_count,
            last_activity_at=datetime.utcnow(),
            next_activity_after=next_activity
        )

        # Update member stats
        member_msg_count = sender.get("message_count", 0) + 1
        update_group_member(
            group_id=group_id,
            account_id=sender_account_id,
            last_message_at=datetime.utcnow(),
            message_count=member_msg_count
        )

        logger.info(
            f"Sent message in group {group_id} from {sender_session_id[:8]}, "
            f"next activity in {next_activity_delay}m"
        )

        return True

    def _choose_message_sender(
        self,
        group: Dict[str, Any],
        members: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Choose who should send the next message.

        Factors:
        - Last message sender (don't repeat)
        - Member activity balance
        - Random factor

        Args:
            group: Group dict
            members: List of group members

        Returns:
            Member dict or None
        """
        if not members:
            return None

        # Get last message sender
        last_message = get_last_group_message(group["id"])
        last_sender_id = last_message.get("sender_account_id") if last_message else None

        # Filter out last sender (avoid monologue)
        available = [m for m in members if m["account_id"] != last_sender_id]

        if not available:
            available = members  # Fallback if only one member

        # Weight by inverse message count (less active members more likely)
        weights = []
        for member in available:
            msg_count = member.get("message_count", 0)
            weight = 1.0 / (msg_count + 1)  # +1 to avoid division by zero
            weights.append(weight)

        # Normalize weights
        total_weight = sum(weights)
        if total_weight == 0:
            return random.choice(available)

        normalized = [w / total_weight for w in weights]

        # Random selection with weights
        r = random.random()
        cumulative = 0
        for member, weight in zip(available, normalized):
            cumulative += weight
            if r <= cumulative:
                return member

        return available[-1]  # Fallback

    async def _generate_group_message(
        self,
        group: Dict[str, Any],
        sender_persona: Dict[str, Any],
        other_personas: List[Dict[str, Any]],
        recent_messages: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Generate a message for group chat.

        Args:
            group: Group dict
            sender_persona: Persona of the sender
            other_personas: Personas of other group members
            recent_messages: Recent messages in the group

        Returns:
            Message text or None
        """
        # Use the conversation agent with group context
        return await self.agent.generate_group_message(
            my_persona=sender_persona,
            group_members=other_personas,
            group_topic=group.get("topic", "общение"),
            group_type=group.get("group_type", "friends"),
            recent_messages=recent_messages
        )

    async def _should_archive_group(self, group: Dict[str, Any]) -> bool:
        """
        Determine if group should be archived.

        Reasons:
        - Too many messages
        - Too old
        - Too few members

        Args:
            group: Group dict

        Returns:
            True if should archive
        """
        message_count = group.get("message_count", 0)
        member_count = group.get("member_count", 0)

        # Hard limit on messages
        if message_count >= self.max_messages_per_group:
            return True

        # Too few members for too long
        if member_count < self.min_members_per_group:
            created_at_str = group.get("created_at")
            if created_at_str:
                try:
                    created_at = datetime.fromisoformat(str(created_at_str))
                    age_hours = (datetime.utcnow() - created_at).total_seconds() / 3600
                    if age_hours > 24:  # 1 day with too few members
                        return True
                except:
                    pass

        # Age limit
        created_at_str = group.get("created_at")
        if created_at_str:
            try:
                created_at = datetime.fromisoformat(str(created_at_str))
                age_days = (datetime.utcnow() - created_at).total_seconds() / 86400
                if age_days > self.max_group_age_days:
                    return True
            except:
                pass

        return False

    async def _archive_group(self, group: Dict[str, Any]):
        """
        Archive a group.

        Args:
            group: Group dict
        """
        group_id = group["id"]
        update_bot_group(
            group_id,
            status="archived",
            next_activity_after=None
        )
        logger.info(f"Archived group {group_id}: '{group.get('group_title')}'")

    def _generate_group_title(self, topic: str, group_type: str) -> str:
        """Generate a natural group title"""
        if group_type == "friends":
            suffixes = ["", " 💬", " ✨", " 🎉"]
            return topic + random.choice(suffixes)
        elif group_type == "thematic":
            prefixes = ["", "Клуб: ", "Чат: "]
            return random.choice(prefixes) + topic
        else:
            return topic

    def _generate_group_description(self, topic: str, group_type: str) -> str:
        """Generate a natural group description"""
        if group_type == "friends":
            return "Дружеский чат для общения"
        elif group_type == "thematic":
            return f"Обсуждение темы: {topic}"
        else:
            return f"Рабочий чат: {topic}"

    async def initiate_new_group_activities(self) -> int:
        """
        Find lonely accounts and create/join groups for them.

        Returns:
            Number of new activities initiated
        """
        # Check if we have room for more groups
        active_count = count_active_bot_groups()
        if active_count >= self.max_active_groups:
            logger.debug(
                f"Max groups reached ({active_count}/{self.max_active_groups})"
            )
            return 0

        # Get accounts that need group membership
        lonely_accounts = get_accounts_without_group_membership(
            min_stage=MIN_STAGE_FOR_DM,
            limit=10
        )

        if len(lonely_accounts) < self.min_members_per_group:
            logger.debug(
                f"Not enough lonely accounts for new group "
                f"({len(lonely_accounts)} < {self.min_members_per_group})"
            )
            return 0

        # Create a new group with some of these accounts
        creator = lonely_accounts[0]
        initial_members = [acc["session_id"] for acc in lonely_accounts[1:self.max_members_per_group]]

        # Choose random group type
        group_type = random.choice(["friends", "thematic"])

        result = await self.create_new_group(
            creator_session_id=creator["session_id"],
            group_type=group_type,
            initial_member_ids=initial_members
        )

        if result:
            logger.info(f"Created new group with {len(initial_members) + 1} members")
            return 1

        return 0


# Singleton instance
_group_engine: Optional[GroupEngine] = None


def get_group_engine(telegram_client: TelegramAPIClient = None) -> GroupEngine:
    """Get singleton instance of GroupEngine"""
    global _group_engine
    if _group_engine is None:
        _group_engine = GroupEngine(telegram_client)
    return _group_engine
