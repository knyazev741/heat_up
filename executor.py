import asyncio
import logging
import random
import json
from typing import List, Dict, Any
from telegram_client import TelegramAPIClient
from config import ACTION_DELAYS
from database import save_session_action

logger = logging.getLogger(__name__)


class ActionExecutor:
    """Executes planned actions with natural timing and error handling"""
    
    def __init__(self, telegram_client: TelegramAPIClient):
        self.telegram_client = telegram_client
        self.joined_channels = set()  # Track joined channels for this session
        
    async def execute_action_plan(
        self, 
        session_id: str, 
        actions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Execute a sequence of actions
        
        Args:
            session_id: Telegram session UID
            actions: List of actions to perform
            
        Returns:
            Execution summary with results
        """
        logger.info(f"Starting action execution for session {session_id} with {len(actions)} actions")
        
        results = []
        errors = []
        
        for idx, action in enumerate(actions, 1):
            action_type = action.get("action")
            
            logger.info("=" * 100)
            logger.info(f"🎬 EXECUTING ACTION #{idx}/{len(actions)}: {action_type.upper()}")
            logger.info("=" * 100)
            logger.info(f"Full action: {json.dumps(action, indent=2, ensure_ascii=False)}")
            logger.info("-" * 100)
            
            try:
                result = await self._execute_single_action(session_id, action)
                success = not result.get("error")
                
                results.append({
                    "step": idx,
                    "action": action,
                    "result": result,
                    "success": success
                })
                
                if result.get("error"):
                    errors.append({
                        "step": idx,
                        "action": action_type,
                        "error": result["error"]
                    })
                    logger.error(f"❌ ACTION FAILED: {result['error']}")
                    logger.error(f"Result details: {json.dumps(result, indent=2, ensure_ascii=False)}")
                else:
                    logger.info(f"✅ ACTION SUCCEEDED: {action_type}")
                    logger.info(f"Result: {json.dumps(result, indent=2, ensure_ascii=False)}")
                    
                    # Save successful action to database
                    try:
                        save_session_action(
                            session_id=session_id,
                            action_type=action_type,
                            action_data=json.dumps(action)
                        )
                        logger.debug("Saved action to database")
                    except Exception as db_error:
                        logger.error(f"Failed to save action to database: {db_error}")
                
                logger.info("=" * 100)
                
            except Exception as e:
                logger.error(f"Unexpected error executing action {action_type}: {str(e)}")
                errors.append({
                    "step": idx,
                    "action": action_type,
                    "error": str(e)
                })
            
            # Natural delay between actions (unless it's the last action)
            if idx < len(actions):
                delay = self._get_natural_delay()
                logger.debug(f"Waiting {delay}s before next action")
                await asyncio.sleep(delay)
        
        summary = {
            "session_id": session_id,
            "total_actions": len(actions),
            "successful_actions": len([r for r in results if r["success"]]),
            "failed_actions": len(errors),
            "results": results,
            "errors": errors,
            "joined_channels": list(self.joined_channels)
        }
        
        logger.info(
            f"Completed execution for session {session_id}: "
            f"{summary['successful_actions']}/{summary['total_actions']} successful"
        )
        
        return summary
    
    async def _execute_single_action(
        self, 
        session_id: str, 
        action: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a single action"""
        
        action_type = action.get("action")
        
        # Check for FloodWait before executing
        if hasattr(self, '_in_floodwait') and self._in_floodwait:
            logger.warning(f"Skipping {action_type} due to FloodWait cooldown")
            return {"error": "Session in FloodWait cooldown", "skipped": True}
        
        if action_type == "join_channel":
            return await self._join_channel(session_id, action)
        elif action_type == "read_messages":
            return await self._read_messages(session_id, action)
        elif action_type == "idle":
            return await self._idle(session_id, action)
        elif action_type == "react_to_message":
            return await self._react_to_message(session_id, action)
        elif action_type == "message_bot":
            return await self._message_bot(session_id, action)
        elif action_type == "view_profile":
            return await self._view_profile(session_id, action)
        elif action_type == "update_profile":
            return await self._update_profile(session_id, action)
        elif action_type == "sync_contacts":
            return await self._sync_contacts(session_id, action)
        elif action_type == "reply_in_chat":
            return await self._reply_in_chat(session_id, action)
        elif action_type == "create_group":
            return await self._create_group(session_id, action)
        elif action_type == "forward_message":
            return await self._forward_message(session_id, action)
        elif action_type == "update_privacy":
            return await self._update_privacy(session_id, action)
        else:
            return {"error": f"Unknown action type: {action_type}"}
    
    async def _join_channel(self, session_id: str, action: Dict[str, Any]) -> Dict[str, Any]:
        """Join a channel"""
        channel_username = action.get("channel_username")
        
        if not channel_username:
            return {"error": "Missing channel_username"}
        
        result = await self.telegram_client.join_chat(session_id, channel_username)
        
        if not result.get("error"):
            self.joined_channels.add(channel_username)
            logger.info(f"Successfully joined {channel_username}")
        
        return result
    
    async def _read_messages(self, session_id: str, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulate reading messages in a channel
        
        According to Telegram's custom client guidelines, we must request
        and display sponsored messages for non-premium users when opening channels/bots.
        """
        channel_username = action.get("channel_username")
        duration = action.get("duration_seconds", 5)
        
        if not channel_username:
            return {"error": "Missing channel_username"}
        
        logger.info(f"Reading messages in {channel_username} for {duration}s")
        
        # Check if user has premium (required by Telegram guidelines)
        session_info = await self.telegram_client.get_session_info(session_id)
        is_premium = False
        
        if not session_info.get("error"):
            is_premium = session_info.get("is_premium", False)
            logger.info(f"📱 Session {session_id} premium status: {is_premium}")
        
        # Get sponsored messages if not premium (Telegram requirement)
        sponsored_ads = []
        if not is_premium:
            logger.info(f"🎯 Non-premium account - fetching official sponsored messages")
            
            sponsored_result = await self.telegram_client.get_sponsored_messages(
                session_id,
                channel_username
            )
            
            if sponsored_result.get("success"):
                result_data = sponsored_result.get("result", {})
                messages = result_data.get("messages", [])
                
                if messages and len(messages) > 0:
                    logger.info(f"📢 Found {len(messages)} sponsored message(s) for {channel_username}")
                    
                    for idx, ad in enumerate(messages, 1):
                        title = ad.get("title", "")
                        message = ad.get("message", "")
                        url = ad.get("url", "")
                        button_text = ad.get("button_text", "")
                        recommended = ad.get("recommended", False)
                        random_id = ad.get("random_id")
                        
                        logger.info(f"  Ad #{idx}:")
                        logger.info(f"    Title: {title}")
                        logger.info(f"    Message: {message[:100]}..." if len(message) > 100 else f"    Message: {message}")
                        logger.info(f"    URL: {url}")
                        logger.info(f"    Button: {button_text}")
                        logger.info(f"    Recommended: {recommended}")
                        
                        sponsored_ads.append({
                            "title": title,
                            "message": message,
                            "url": url,
                            "button_text": button_text,
                            "recommended": recommended,
                            "random_id": random_id
                        })
                        
                        # Mark as viewed (required by Telegram guidelines)
                        if random_id:
                            try:
                                await self.telegram_client.view_sponsored_message(
                                    session_id,
                                    random_id
                                )
                                logger.debug(f"    ✓ Marked ad #{idx} as viewed")
                            except Exception as e:
                                logger.warning(f"    ⚠ Failed to mark ad as viewed: {e}")
                else:
                    logger.info(f"📭 No sponsored messages available for {channel_username}")
            elif "AD_EXPIRED" in str(sponsored_result.get("error", "")):
                logger.info(f"⏰ Sponsored messages expired for {channel_username}")
            elif "PREMIUM_ACCOUNT_REQUIRED" in str(sponsored_result.get("error", "")):
                logger.info(f"💎 Account is actually premium (server says so)")
            else:
                logger.warning(f"⚠ Could not fetch sponsored messages: {sponsored_result.get('error')}")
        else:
            logger.info(f"💎 Premium account - skipping sponsored messages")
        
        # Get dialogs to simulate activity
        result = await self.telegram_client.get_dialogs(session_id)
        
        # Wait for the specified duration to simulate reading
        await asyncio.sleep(duration)
        
        response = {
            "action": "read_messages",
            "channel": channel_username,
            "duration": duration,
            "status": "completed",
            "is_premium": is_premium
        }
        
        if sponsored_ads:
            response["sponsored_ads_count"] = len(sponsored_ads)
            response["sponsored_ads"] = sponsored_ads
        
        return response
    
    async def _idle(self, session_id: str, action: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate idle/break time"""
        duration = action.get("duration_seconds", 5)
        
        logger.info(f"Going idle for {duration}s")
        
        # Optionally set the session to idle state
        # await self.telegram_client.set_idle(session_id)
        
        await asyncio.sleep(duration)
        
        return {
            "action": "idle",
            "duration": duration,
            "status": "completed"
        }
    
    async def _react_to_message(self, session_id: str, action: Dict[str, Any]) -> Dict[str, Any]:
        """React to a message in a channel - only uses reactions that are already present"""
        channel_username = action.get("channel_username")
        
        if not channel_username:
            return {"error": "Missing channel_username"}
        
        # Get recent messages from the channel first
        messages_result = await self.telegram_client.get_channel_messages(
            session_id, 
            channel_username, 
            limit=10
        )
        
        # If we got messages, try to find ones with existing reactions
        if not messages_result.get("error") and messages_result.get("result"):
            try:
                messages = messages_result["result"]
                if messages and len(messages) > 0:
                    # Collect messages that have reactions (means reactions are enabled and allowed)
                    messages_with_reactions = []
                    available_emojis = set()
                    
                    for msg in messages:
                        reactions = msg.get("reactions")
                        if reactions and isinstance(reactions, list) and len(reactions) > 0:
                            # Extract emojis from reactions
                            msg_emojis = []
                            for reaction in reactions:
                                emoji = reaction.get("emoji") or reaction.get("emoticon")
                                if emoji:
                                    msg_emojis.append(emoji)
                                    available_emojis.add(emoji)
                            
                            if msg_emojis:
                                messages_with_reactions.append({
                                    "id": msg.get("id"),
                                    "emojis": msg_emojis
                                })
                    
                    # If we found messages with reactions, react to one
                    if messages_with_reactions and available_emojis:
                        # Pick a random message that has reactions
                        target_message = random.choice(messages_with_reactions)
                        message_id = target_message["id"]
                        
                        # Pick a random emoji from the ones already used on messages
                        emoji = random.choice(list(available_emojis))
                        
                        logger.info(f"Found {len(available_emojis)} allowed emojis in {channel_username}: {available_emojis}")
                        logger.info(f"Reacting with {emoji} to message {message_id}")
                        
                        result = await self.telegram_client.send_reaction(
                            session_id,
                            channel_username,
                            message_id,
                            emoji
                        )
                        
                        return result
                    else:
                        # No reactions found on any messages - reactions might be disabled
                        logger.info(f"No existing reactions found in {channel_username} - reactions might be disabled. Skipping.")
                        return {
                            "action": "react_to_message",
                            "channel": channel_username,
                            "status": "skipped",
                            "reason": "No reactions found on messages (reactions might be disabled in this channel)"
                        }
                        
            except Exception as e:
                logger.error(f"Error processing messages for reaction: {e}")
        
        # If no messages or error, just simulate
        logger.info(f"Cannot react in {channel_username} - no messages or error getting them")
        return {
            "action": "react_to_message",
            "channel": channel_username,
            "status": "skipped",
            "reason": "Could not get messages from channel"
        }
    
    async def _message_bot(self, session_id: str, action: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message to a bot"""
        bot_username = action.get("bot_username")
        message = action.get("message", "/start")
        
        if not bot_username:
            return {"error": "Missing bot_username"}
        
        logger.info(f"Sending message to bot {bot_username}: {message}")
        
        result = await self.telegram_client.send_message(
            session_id,
            bot_username,
            message,
            disable_notification=True
        )
        
        # Wait a bit to simulate reading bot response
        await asyncio.sleep(random.uniform(2, 5))
        
        return result
    
    async def _view_profile(self, session_id: str, action: Dict[str, Any]) -> Dict[str, Any]:
        """View a channel's profile/information"""
        channel_username = action.get("channel_username")
        duration = action.get("duration_seconds", 5)
        
        if not channel_username:
            return {"error": "Missing channel_username"}
        
        logger.info(f"Viewing profile of {channel_username} for {duration}s")
        
        # Simulate viewing profile by getting channel info
        result = await self.telegram_client.get_dialogs(session_id, limit=10)
        
        # Wait for the specified duration to simulate reading profile
        await asyncio.sleep(duration)
        
        return {
            "action": "view_profile",
            "channel": channel_username,
            "duration": duration,
            "status": "completed"
        }
    
    async def _update_profile(self, session_id: str, action: Dict[str, Any]) -> Dict[str, Any]:
        """Update profile information"""
        from telegram_tl_helpers import make_update_profile_query
        
        first_name = action.get("first_name")
        last_name = action.get("last_name")
        bio = action.get("bio")
        
        logger.info(f"Updating profile for session {session_id}: {first_name} {last_name}")
        
        try:
            # Create TL query for profile update
            query = make_update_profile_query(
                first_name=first_name,
                last_name=last_name,
                about=bio  # 'about' is the TL field for bio
            )
            
            logger.debug(f"Profile update query: {query}")
            
            # Execute via telegram_client
            response = await self.telegram_client.invoke_raw(
                session_id=session_id,
                query=query,
                retries=3,
                timeout=15
            )
            
            if response.get("success"):
                logger.info(f"Profile updated successfully for session {session_id}")
                return {
                    "action": "update_profile",
                    "status": "completed",
                    "first_name": first_name,
                    "last_name": last_name,
                    "bio": bio,
                    "telegram_response": response.get("result")
                }
            else:
                error_msg = response.get("error", "Unknown error")
                logger.error(f"Failed to update profile for session {session_id}: {error_msg}")
                
                # Check if session is frozen
                if "frozen" in error_msg.lower():
                    return {
                        "action": "update_profile",
                        "status": "failed",
                        "error": "Session is frozen",
                        "first_name": first_name,
                        "last_name": last_name,
                        "bio": bio
                    }
                
                return {
                    "action": "update_profile",
                    "status": "failed",
                    "error": error_msg,
                    "first_name": first_name,
                    "last_name": last_name,
                    "bio": bio
                }
                
        except Exception as e:
            logger.error(f"Exception during profile update for session {session_id}: {str(e)}")
            return {
                "action": "update_profile",
                "status": "failed",
                "error": str(e),
                "first_name": first_name,
                "last_name": last_name,
                "bio": bio
            }
    
    async def _sync_contacts(self, session_id: str, action: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronize contacts"""
        logger.info("Syncing contacts")
        
        # Simulate contact sync - in real implementation would use sync_contacts RPC
        await asyncio.sleep(random.uniform(2, 5))
        
        return {
            "action": "sync_contacts",
            "status": "completed",
            "synced_contacts": 0  # Placeholder
        }
    
    async def _reply_in_chat(self, session_id: str, action: Dict[str, Any]) -> Dict[str, Any]:
        """Reply to a message in a chat"""
        chat_username = action.get("chat_username")
        reply_text = action.get("reply_text", "")
        
        if not chat_username:
            return {"error": "Missing chat_username"}
        
        if not reply_text:
            reply_text = "Interesting! Thanks for sharing."
        
        logger.info(f"Replying in {chat_username}: {reply_text[:50]}...")
        
        # Check for FloodWait keywords in reply
        if self._check_floodwait_keywords(reply_text):
            return {"error": "Reply text contains potential spam keywords"}
        
        try:
            # Send the message
            result = await self.telegram_client.send_message(
                session_id,
                chat_username,
                reply_text,
                disable_notification=True
            )
            
            # Check for FloodWait error
            if result.get("error"):
                error_text = str(result.get("error", "")).lower()
                if "flood" in error_text or "wait" in error_text:
                    logger.error(f"⚠️ FLOODWAIT DETECTED for session {session_id}")
                    self._in_floodwait = True
                    from database import update_account
                    from database import get_account
                    account = get_account(session_id)
                    if account:
                        update_account(session_id, is_frozen=True)
            
            return result
        except Exception as e:
            logger.error(f"Error replying in chat: {e}")
            return {"error": str(e)}
    
    async def _create_group(self, session_id: str, action: Dict[str, Any]) -> Dict[str, Any]:
        """Create a group"""
        group_name = action.get("group_name", "My Group")
        
        logger.info(f"Creating group: {group_name}")
        
        # For now, simulated - would use create_group RPC in real implementation
        await asyncio.sleep(random.uniform(3, 6))
        
        return {
            "action": "create_group",
            "group_name": group_name,
            "status": "completed"
        }
    
    async def _forward_message(self, session_id: str, action: Dict[str, Any]) -> Dict[str, Any]:
        """Forward a message"""
        from_chat = action.get("from_chat")
        to_chat = action.get("to_chat")
        
        if not from_chat or not to_chat:
            return {"error": "Missing from_chat or to_chat"}
        
        logger.info(f"Forwarding message from {from_chat} to {to_chat}")
        
        # For now, simulated - would use ForwardMessages TL method
        await asyncio.sleep(random.uniform(2, 4))
        
        return {
            "action": "forward_message",
            "from_chat": from_chat,
            "to_chat": to_chat,
            "status": "completed"
        }
    
    async def _update_privacy(self, session_id: str, action: Dict[str, Any]) -> Dict[str, Any]:
        """Update privacy settings"""
        logger.info("Updating privacy settings")
        
        # Recommended privacy settings for warmup
        privacy_settings = {
            "phone_number": "contacts",  # Only contacts can see phone
            "profile_photo": "everyone",  # Everyone can see photo (green flag!)
            "forwards": "everyone",  # Allow forwards
            "calls": "contacts"  # Only contacts can call
        }
        
        # Simulate setting privacy
        await asyncio.sleep(random.uniform(3, 6))
        
        return {
            "action": "update_privacy",
            "settings": privacy_settings,
            "status": "completed"
        }
    
    def _check_floodwait_keywords(self, text: str) -> bool:
        """Check if text contains potential spam keywords"""
        spam_keywords = [
            "buy now", "click here", "limited offer", "act now",
            "free money", "earn $", "make money fast"
        ]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in spam_keywords)
    
    def _get_natural_delay(self) -> float:
        """Get a randomized natural delay between actions"""
        min_delay = ACTION_DELAYS["min_between_actions"]
        max_delay = ACTION_DELAYS["max_between_actions"]
        
        # Use a slight bias toward shorter delays for more activity
        delay = random.uniform(min_delay, max_delay)
        
        # Add occasional longer pauses (10% chance)
        if random.random() < 0.1:
            delay += random.uniform(5, 10)
        
        return round(delay, 2)

