import asyncio
import logging
import random
import json
from typing import List, Dict, Any
from telegram_client import TelegramAPIClient
from config import ACTION_DELAYS
from database import save_session_action, update_account, get_account, is_chat_joined, can_join_channel, get_behavioral_profile, DEFAULT_BEHAVIORAL_PROFILE

logger = logging.getLogger(__name__)

# Critical Telegram errors that indicate session is dead/revoked
# When these occur, session should be marked as deleted and removed from warmup
CRITICAL_SESSION_ERRORS = [
    "AUTH_KEY_UNREGISTERED",      # Session key was revoked/deleted
    "SESSION_REVOKED",            # Session was explicitly revoked
    "USER_DEACTIVATED",           # User account was deleted
    "USER_DEACTIVATED_BAN",       # User was banned by Telegram
    "SESSION_EXPIRED",            # Session expired
    "AUTH_KEY_DUPLICATED",        # Auth key used in another session
    "AUTH_KEY_PERM_EMPTY",        # Permanent auth key is empty
]


def _is_critical_session_error(error_text: str) -> str | None:
    """
    Check if error indicates a dead/revoked session

    Args:
        error_text: Error message string

    Returns:
        Error code if critical, None otherwise
    """
    if not error_text:
        return None
    error_upper = str(error_text).upper()
    for error_code in CRITICAL_SESSION_ERRORS:
        if error_code in error_upper:
            return error_code
    return None


class ActionExecutor:
    """Executes planned actions with natural timing and error handling"""
    
    def __init__(self, telegram_client: TelegramAPIClient):
        self.telegram_client = telegram_client
        self.joined_channels = set()  # Track joined channels for this session
        
    async def execute_action_plan(
        self,
        session_id: str,
        actions: List[Dict[str, Any]],
        account_id: int = None,
        passive_only: bool = False
    ) -> Dict[str, Any]:
        """
        Execute a sequence of actions

        Args:
            session_id: Telegram session UID
            actions: List of actions to perform
            account_id: Account ID for loading behavioral profile
            passive_only: If True, skip aggressive actions (join, send, reply, etc.)

        Returns:
            Execution summary with results
        """
        # Load behavioral profile for this account
        if account_id:
            self._current_profile = get_behavioral_profile(account_id)
        else:
            self._current_profile = DEFAULT_BEHAVIORAL_PROFILE.copy()

        # Safety net: filter out aggressive actions in passive mode
        if passive_only:
            PASSIVE_ACTIONS = {"read_messages", "view_profile", "idle"}
            original_count = len(actions)
            actions = [a for a in actions if a.get("action") in PASSIVE_ACTIONS]
            if len(actions) < original_count:
                logger.warning(
                    f"👁️ Passive mode: filtered {original_count - len(actions)} aggressive actions, "
                    f"keeping {len(actions)} passive actions"
                )

        logger.info(f"Starting action execution for session {session_id} with {len(actions)} actions" + (" [PASSIVE]" if passive_only else ""))
        
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

                    # Check for frozen session error
                    if "frozen" in str(result["error"]).lower():
                        logger.error(f"❄️ SESSION FROZEN: {session_id}")
                        update_account(session_id, is_frozen=True)
                        # Record to freeze journal
                        try:
                            from freeze_journal import record_freeze_event
                            record_freeze_event(session_id, freeze_source="rpc_error")
                        except Exception as je:
                            logger.error(f"Failed to record freeze event: {je}")
                        return {
                            "session_id": session_id,
                            "total_actions": len(actions),
                            "executed": idx,
                            "successful": idx - len(errors),
                            "failed": len(errors),
                            "results": results,
                            "errors": errors,
                            "session_frozen": True
                        }

                    # Check for critical session errors (dead/revoked session)
                    critical_error = _is_critical_session_error(result["error"])
                    if critical_error:
                        logger.error(f"🚨 CRITICAL SESSION ERROR: {critical_error}")
                        logger.error(f"🚨 Marking session {session_id} as DELETED and stopping execution")
                        update_account(session_id, is_deleted=True)
                        return {
                            "session_id": session_id,
                            "total_actions": len(actions),
                            "executed": idx,
                            "successful": idx - len(errors),
                            "failed": len(errors),
                            "results": results,
                            "errors": errors,
                            "critical_error": critical_error,
                            "session_marked_deleted": True
                        }
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
        
        if action_type in {"join_channel", "join_chat"}:
            return await self._join_channel(session_id, action)
        elif action_type in {"read_messages", "read_chat_messages"}:
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
        elif action_type == "reply_to_dm":
            return await self._reply_to_dm(session_id, action)
        else:
            return {"error": f"Unknown action type: {action_type}"}
    
    async def _join_channel(self, session_id: str, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Join a chat or channel.

        According to Telegram's custom client guidelines, we must request
        and display sponsored messages for non-premium users when opening channels/bots.
        """
        chat_username = action.get("chat_username") or action.get("channel_username")
        if not chat_username:
            return {"error": "Missing chat_username"}

        chat_type = (action.get("chat_type") or "").lower()
        logger.info(f"🚪 Attempting to join {chat_username} (type: {chat_type or 'unknown'})")

        # Get account_id for spam protection checks
        account = get_account(session_id)
        if not account:
            logger.error(f"❌ Account not found for session {session_id} - blocking join for safety")
            return {
                "action": "join_channel",
                "chat_username": chat_username,
                "status": "error",
                "reason": "Account not found in database"
            }
        account_id = account["id"]

        # CHECK 1: Already joined?
        if is_chat_joined(account_id, chat_username):
            logger.info(f"✅ Already joined {chat_username}, skipping duplicate join")
            return {
                "action": "join_channel",
                "chat_username": chat_username,
                "status": "skipped",
                "reason": "Already joined"
            }

        # CHECK 2: Rate limiting + exclusivity (limits from behavioral profile)
        bp = getattr(self, '_current_profile', None) or DEFAULT_BEHAVIORAL_PROFILE
        bp_join = bp.get("joining", DEFAULT_BEHAVIORAL_PROFILE["joining"])
        can_join, reason = can_join_channel(
            account_id, chat_username,
            max_per_hour=bp_join.get("max_per_hour", 3),
            min_interval_minutes=bp_join.get("min_interval_minutes", 10)
        )
        if not can_join:
            logger.info(f"⏱️ Rate limit/exclusivity for {chat_username}: {reason}")
            return {
                "action": "join_channel",
                "chat_username": chat_username,
                "status": "rate_limited",
                "reason": reason
            }

        # Check if user has premium (required by Telegram guidelines)
        session_info = await self.telegram_client.get_session_info(session_id)
        is_premium = False

        if not session_info.get("error"):
            is_premium = session_info.get("is_premium", False)
            logger.info(f"📱 Session {session_id} premium status: {is_premium}")
        else:
            logger.warning(f"⚠️ Could not determine premium status: {session_info.get('error')}")

        # Проверяем существование чата через высокоуровневое API
        resolved_chat: Dict[str, Any] = {}
        logger.info(f"🔍 Checking if chat {chat_username} exists...")
        try:
            resolve_result = await self.telegram_client.resolve_chat(session_id, chat_username)

            if resolve_result.get("success"):
                resolved_chat = resolve_result.get("result", {}).get("chat") or {}
                if isinstance(resolved_chat, dict) and resolved_chat.get("type"):
                    chat_type = resolved_chat.get("type", chat_type).lower()
                logger.info(f"✅ Chat {chat_username} exists (type: {chat_type or 'unknown'})")
            else:
                error = resolve_result.get("error", "")
                error_code = resolve_result.get("error_code", "")

                if error_code in ["USERNAME_NOT_OCCUPIED", "USERNAME_INVALID", "INVALID_USERNAME"]:
                    logger.warning(f"❌ Chat {chat_username} does NOT exist ({error_code})")
                    return {
                        "error": f"Chat {chat_username} not found ({error_code})",
                        "success": False,
                        "channel_not_found": True
                    }
                elif error_code == "CHANNEL_INVALID":
                    logger.warning(f"❌ Chat {chat_username} is invalid or deleted")
                    return {
                        "error": f"Chat {chat_username} is invalid",
                        "success": False,
                        "channel_not_found": True
                    }
                else:
                    logger.warning(f"⚠️ Error resolving {chat_username}: {error} (code: {error_code})")
                    logger.info("⚠️ Will try to join anyway...")
        except Exception as exc:
            logger.warning(f"⚠️ Could not verify chat existence: {exc}")
        # Get sponsored messages if required (only for channel-like entities)
        sponsored_ads = []
        # Рекламу запрашиваем ПОСЛЕ вступления в канал (per Telegram docs)
        should_fetch_ads = not is_premium and chat_type not in {"group", "supergroup", "private"}

        # Check supergroup limits before joining
        if chat_type in {"group", "supergroup"}:
            # Resolve peer to determine exact type (megagroup = supergroup)
            try:
                peer_result = await self.telegram_client.resolve_peer(session_id, chat_username)
                if peer_result.get("success"):
                    chat_data = peer_result.get("chat_data", {})
                    if chat_data.get("megagroup"):
                        # This is a supergroup - check limits
                        from database import can_join_supergroup
                        acc = get_account(session_id)
                        if acc:
                            warmup_stage = acc.get('warmup_stage', 0)
                            can_join, reason = can_join_supergroup(acc['id'], warmup_stage)
                            if not can_join:
                                logger.info(f"🚫 Cannot join supergroup {chat_username}: {reason}")
                                return {
                                    "action": "join_channel",
                                    "status": "skipped",
                                    "reason": reason,
                                    "chat_type": "supergroup"
                                }
                            logger.info(f"✅ Supergroup join allowed: {reason}")
            except Exception as exc:
                logger.warning(f"Could not check supergroup limits: {exc}")

        # Now join the chat
        result = await self.telegram_client.join_chat(session_id, chat_username)

        error_str = str(result.get("error", "")).upper()

        # Handle "already in chat" as success - just update our database
        if "ALREADY" in error_str or "USER_ALREADY_PARTICIPANT" in error_str:
            logger.info(f"✅ Already a member of {chat_username} - updating database")
            self.joined_channels.add(chat_username)

            # Update database to mark as joined — but check exclusivity first
            try:
                from database import update_chat_joined, is_chat_exclusive_for_warmup
                acc = get_account(session_id)
                if acc:
                    # Check exclusivity for warmup accounts before syncing to DB
                    if acc.get("account_type") == "warmup":
                        is_exclusive, existing_id = is_chat_exclusive_for_warmup(acc['id'], chat_username)
                        if not is_exclusive:
                            logger.warning(
                                f"⚠️ NOT syncing {chat_username} for warmup account {acc['id']}: "
                                f"chat occupied by warmup account {existing_id} (exclusivity violation)"
                            )
                            return {
                                "action": "join_channel",
                                "chat_username": chat_username,
                                "status": "already_joined_blocked",
                                "success": False,
                                "message": f"Already joined but chat occupied by warmup {existing_id}"
                            }
                    update_chat_joined(acc['id'], chat_username, chat_type or 'unknown')
                    logger.info(f"✅ Synced {chat_username} membership to database")
            except Exception as exc:
                logger.error(f"Failed to sync membership to database: {exc}")

            return {
                "action": "join_channel",
                "chat_username": chat_username,
                "status": "already_joined",
                "success": True,
                "message": "Already a member, database synced"
            }

        if not result.get("error"):
            self.joined_channels.add(chat_username)
            logger.info(f"Successfully joined {chat_username}")

            # Get accurate chat_type from resolve_peer (megagroup/broadcast)
            real_chat_type = chat_type  # fallback to resolved type
            try:
                peer_result = await self.telegram_client.resolve_peer(session_id, chat_username)
                if peer_result.get("success"):
                    chat_data = peer_result.get("chat_data", {})
                    if chat_data.get("megagroup"):
                        real_chat_type = "supergroup"
                    elif chat_data.get("broadcast"):
                        real_chat_type = "channel"
                    logger.info(f"📋 Detected real chat type: {real_chat_type}")
            except Exception as exc:
                logger.warning(f"Could not detect real chat type: {exc}")

            # Update database - mark chat as joined with correct type
            try:
                from database import update_chat_joined
                acc = get_account(session_id)
                if acc:
                    update_chat_joined(acc['id'], chat_username, real_chat_type)
                    logger.info(f"✅ Marked {chat_username} as joined (type: {real_chat_type})")
                else:
                    logger.warning(f"Could not find account for session {session_id} to update joined status")
            except Exception as exc:
                logger.error(f"Failed to update joined status in database: {exc}")

            # Запрашиваем рекламу ПОСЛЕ успешного вступления (per Telegram docs)
            if should_fetch_ads:
                logger.info("📢 User joined channel - fetching sponsored ads...")
                sponsored_result = await self.telegram_client.get_sponsored_messages(
                    session_id,
                    chat_username
                )

                if sponsored_result.get("success"):
                    result_data = sponsored_result.get("result", {})
                    ad_messages = result_data.get("messages", [])

                    if ad_messages:
                        logger.info(f"📢 Found {len(ad_messages)} sponsored message(s) for {chat_username}")
                        for idx, ad in enumerate(ad_messages, 1):
                            title = ad.get("title", "")
                            message_text = ad.get("message", "")
                            url = ad.get("url", "")
                            button_text = ad.get("button_text", "")
                            recommended = ad.get("recommended", False)
                            random_id = ad.get("random_id")

                            logger.info(f"  Ad #{idx}: {title[:50]}..." if len(title) > 50 else f"  Ad #{idx}: {title}")

                            sponsored_ads.append({
                                "title": title,
                                "message": message_text,
                                "url": url,
                                "button_text": button_text,
                                "recommended": recommended,
                                "random_id": random_id
                            })

                            if random_id:
                                try:
                                    await self.telegram_client.view_sponsored_message(session_id, random_id)
                                    logger.debug(f"    ✓ Marked ad #{idx} as viewed")
                                except Exception as exc:
                                    logger.warning(f"    ⚠ Failed to mark ad as viewed: {exc}")
                    else:
                        logger.info(f"📭 No sponsored messages available for {chat_username}")
                elif "AD_EXPIRED" in str(sponsored_result.get("error", "")):
                    logger.info(f"⏰ Sponsored messages expired for {chat_username}")
                elif "PREMIUM_ACCOUNT_REQUIRED" in str(sponsored_result.get("error", "")):
                    logger.info("💎 Account is actually premium (server says so)")
                else:
                    logger.warning(f"⚠ Could not fetch sponsored messages: {sponsored_result.get('error')}")

        # Add sponsored ads info to result
        if sponsored_ads:
            result["sponsored_ads_count"] = len(sponsored_ads)
            result["sponsored_ads"] = sponsored_ads

        result["is_premium"] = is_premium
        if chat_type:
            result["chat_type"] = chat_type
        if resolved_chat:
            result["chat_meta"] = resolved_chat

        return result

    async def _read_messages(self, session_id: str, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Read messages in a chat or channel and report unread counts
        
        Features:
        - Marks messages as read correctly using top_message_id
        - Random chance to react to messages (10%)
        - Random chance to save to favorites (5%)
        - Skip/quick scroll simulation (15%)
        """
        chat_username = action.get("chat_username") or action.get("channel_username")
        duration = action.get("duration_seconds", 5)

        if not chat_username:
            return {"error": "Missing chat_username"}

        logger.info(f"Reading messages in {chat_username} for {duration}s")

        session_info = await self.telegram_client.get_session_info(session_id)
        is_premium = False

        if not session_info.get("error"):
            is_premium = session_info.get("is_premium", False)
            logger.info(f"📱 Session {session_id} premium status: {is_premium}")
        else:
            logger.warning(f"⚠️ Could not determine premium status: {session_info.get('error')}")

        resolved_peer = await self.telegram_client.resolve_peer(session_id, chat_username)
        if not resolved_peer.get("success"):
            error_msg = resolved_peer.get("error", "Failed to resolve chat")
            logger.error(f"❌ Cannot resolve chat {chat_username}: {error_msg}")
            return {"error": error_msg, "success": False}

        chat_type = (action.get("chat_type") or resolved_peer.get("chat_type") or resolved_peer.get("peer_type") or "").lower()
        sponsored_ads = []
        # По документации Telegram, реклама отображается ПОСЛЕ того как пользователь
        # прокрутил все сообщения в канале и дошёл до конца.
        # Поэтому запрашиваем рекламу ПОСЛЕ чтения сообщений, а не до.
        should_fetch_ads = not is_premium and chat_type not in {"group", "supergroup", "private"}

        unread_count = None
        read_inbox_max_id = 0
        top_message_id = 0
        
        dialog_info = await self.telegram_client.get_peer_dialog(session_id, resolved_peer)
        if dialog_info.get("success"):
            unread_count = dialog_info.get("unread_count", 0)
            read_inbox_max_id = dialog_info.get("read_inbox_max_id", 0)
            top_message_id = dialog_info.get("top_message", 0)
            logger.info(f"📨 Unread messages in {chat_username}: {unread_count}")
            if unread_count > 0:
                logger.info(f"   First unread: #{read_inbox_max_id + 1}, Last: #{top_message_id}")
        else:
            logger.warning(f"⚠️ Could not get dialog info for {chat_username}: {dialog_info.get('error')}")

        messages_read = 0
        messages_texts = []
        last_message_id = 0
        actual_read_time = 0.0
        reactions_sent = 0
        messages_saved = 0
        # Читаем сообщения правильно - с первого непрочитанного к последнему
        # Это имитирует поведение официального клиента: открыть чат, увидеть где остановились, 
        # и листать вверх к новым сообщениям
        if unread_count and unread_count > 0:
            # Ограничиваем максимум для безопасности (не более 50 за раз)
            max_messages_to_read = min(unread_count, 50)
            first_unread_id = read_inbox_max_id + 1
            
            logger.info(f"📥 Reading {max_messages_to_read} unread messages starting from #{first_unread_id}...")
            logger.info(f"   Strategy: fetch from top_message #{top_message_id} going back {max_messages_to_read} messages")
            
            # ПРАВИЛЬНЫЙ СПОСОБ как в официальном клиенте:
            # Используем offset_id = top_message_id + 1 (начинаем после последнего сообщения)
            # add_offset = 0 - не пропускаем
            # limit = unread_count - получаем ровно столько, сколько непрочитанных
            # Это даёт нам последние N сообщений (которые и есть непрочитанные)
            from telegram_tl_helpers import make_get_history_query
            
            query = make_get_history_query(
                peer=resolved_peer['input_peer'],
                offset_id=top_message_id + 1,  # Начинаем "после" последнего, чтобы он вошёл в выборку
                add_offset=0,
                limit=max_messages_to_read,
                min_id=read_inbox_max_id,  # Только сообщения с ID > read_inbox_max_id (непрочитанные)
                max_id=0,
                hash=0
            )
            
            history_result = await self.telegram_client.invoke_raw(session_id, query)
            
            if not history_result.get("error"):
                try:
                    result_data = history_result.get("result") or {}
                    if isinstance(result_data, dict):
                        messages = result_data.get("messages", [])
                    elif isinstance(result_data, list):
                        messages = result_data
                    else:
                        messages = []

                    # ФИЛЬТРУЕМ: только сообщения с ID > read_inbox_max_id (непрочитанные)
                    unread_messages = [m for m in messages if m.get('id', 0) > read_inbox_max_id]
                    
                    # Сортируем от старых к новым (как читает человек - от первого непрочитанного к последнему)
                    messages_sorted = sorted(unread_messages, key=lambda m: m.get('id', 0))
                    
                    # Детальное логирование для отладки
                    if messages:
                        raw_ids = sorted([m.get('id', 0) for m in messages])
                        logger.info(f"📥 API returned {len(messages)} messages (IDs {raw_ids[0]} - {raw_ids[-1]})")
                    else:
                        logger.info(f"📥 API returned 0 messages")
                    
                    logger.info(f"   After filtering ID > {read_inbox_max_id}: {len(messages_sorted)} unread messages")
                    
                    if messages_sorted:
                        logger.info(f"   ✅ Unread range: #{messages_sorted[0].get('id')} - #{messages_sorted[-1].get('id')}")
                        
                        # КРИТИЧЕСКИ ВАЖНО: Отмечаем как прочитанное СРАЗУ после получения сообщений
                        # НЕ ждём завершения симуляции чтения - это гарантирует что mark_read всегда вызовется
                        mark_up_to_id = top_message_id if top_message_id > 0 else messages_sorted[-1].get('id', 0)
                        if mark_up_to_id > 0:
                            mark_result = await self.telegram_client.mark_history_read(session_id, resolved_peer, max_id=mark_up_to_id)
                            if not mark_result.get("error"):
                                logger.info(f"   👁️ Marked messages up to #{mark_up_to_id} as read")
                            else:
                                logger.warning(f"   ⚠️ Failed to mark as read: {mark_result.get('error')}")
                        
                    elif messages:
                        logger.warning(f"   ⚠️ All {len(messages)} fetched messages were already read (ID <= {read_inbox_max_id})")
                        logger.warning(f"   This suggests API returned wrong offset. Expected ID > {read_inbox_max_id}")

                    # Параметры случайного поведения из behavioral profile
                    bp = getattr(self, '_current_profile', None) or DEFAULT_BEHAVIORAL_PROFILE
                    bp_eng = bp.get("engagement", DEFAULT_BEHAVIORAL_PROFILE["engagement"])
                    skip_probability = bp_eng.get("skip_probability", 0.15) if len(messages_sorted) >= 3 else 0
                    react_probability = bp_eng.get("react_probability", 0.10)
                    save_probability = bp_eng.get("save_probability_long", 0.05)
                    save_probability_short = bp_eng.get("save_probability_short", 0.03)
                    
                    # ВАЖНО: Ограничиваем время на чтение чтобы успеть вызвать mark_read
                    time_budget = duration - 2.0  # Оставляем 2 секунды на mark_read
                    time_budget = max(time_budget, 5.0)  # Минимум 5 секунд на чтение
                    
                    for i, msg in enumerate(messages_sorted):
                        # Проверяем бюджет времени ПЕРЕД обработкой сообщения
                        if actual_read_time >= time_budget:
                            logger.info(f"   ⏱️ Time budget exhausted ({actual_read_time:.1f}s / {time_budget:.1f}s), stopping at msg {i+1}/{len(messages_sorted)}")
                            break
                        
                        msg_id = msg.get("id")
                        if isinstance(msg_id, int):
                            last_message_id = max(last_message_id, msg_id)
                        
                        msg_text = msg.get("message") or msg.get("text", "")
                        text_length = len(msg_text)
                        
                        # Вычисляем время чтения для этого сообщения
                        is_skipped = random.random() < skip_probability
                        if is_skipped:
                            # Быстрое пролистывание - не вникая
                            msg_read_time = random.uniform(0.3, 0.8)
                        else:
                            # Реальное чтение с параметрами из behavioral profile
                            bp_read = bp.get("reading", DEFAULT_BEHAVIORAL_PROFILE["reading"])
                            base_time = 1.0
                            reading_speed = random.uniform(
                                bp_read.get("speed_min", 3),
                                bp_read.get("speed_max", 6)
                            )
                            reading_time = text_length / reading_speed if text_length > 0 else 0
                            thinking_time = random.uniform(
                                bp_read.get("thinking_time_min", 0.5),
                                bp_read.get("thinking_time_max", 2.0)
                            )

                            msg_read_time = base_time + reading_time + thinking_time
                            max_read = bp_read.get("max_read_time", 5.0)
                            msg_read_time = min(msg_read_time, max_read)
                        
                        actual_read_time += msg_read_time
                        
                        if msg_text:
                            text_preview = msg_text[:200] + "..." if len(msg_text) > 200 else msg_text
                            if i < 3:  # Логируем первые 3
                                logger.info(f"  📬 Msg #{msg.get('id', '?')} ({text_length} chars, {msg_read_time:.1f}s): {text_preview[:80]}...")
                            messages_texts.append(text_preview)
                            messages_read += 1
                        else:
                            media_type = msg.get("media", {}).get("_", "unknown") if msg.get("media") else "no media"
                            if i < 3:
                                logger.info(f"  📷 Msg #{msg.get('id', '?')} ({msg_read_time:.1f}s): [media: {media_type}]")
                            messages_read += 1
                        
                        # Имитируем чтение этого сообщения
                        await asyncio.sleep(msg_read_time)
                        
                        # === ENGAGEMENT FEATURES ===
                        
                        # Шанс поставить реакцию (только если не пролистали быстро)
                        # ВАЖНО: Используем ТОЛЬКО реакции которые уже есть на этом сообщении
                        if not is_skipped and msg_id and random.random() < react_probability:
                            try:
                                # Получаем список реакций из самого сообщения
                                msg_reactions = msg.get("reactions", {})
                                available_reactions = []
                                
                                # Извлекаем emoji из реакций на сообщении
                                if isinstance(msg_reactions, dict):
                                    results = msg_reactions.get("results", [])
                                    for r in results:
                                        if isinstance(r, dict):
                                            reaction = r.get("reaction", {})
                                            if isinstance(reaction, dict):
                                                # Может быть reactionEmoji или reactionCustomEmoji
                                                emoticon = reaction.get("emoticon")
                                                if emoticon:
                                                    available_reactions.append(emoticon)
                                
                                if available_reactions:
                                    # Выбираем случайную реакцию из доступных на сообщении
                                    reaction_emoji = random.choice(available_reactions)
                                    react_result = await self.telegram_client.send_reaction(
                                        session_id, chat_username, msg_id, reaction_emoji
                                    )
                                    if not react_result.get("error"):
                                        reactions_sent += 1
                                        logger.info(f"  💬 Reacted with {reaction_emoji} to msg #{msg_id}")
                                    else:
                                        logger.debug(f"  ⚠️ Could not react: {react_result.get('error')}")
                                else:
                                    logger.debug(f"  ℹ️ No reactions available on msg #{msg_id}")
                            except Exception as e:
                                logger.debug(f"  ⚠️ Reaction failed: {e}")
                        
                        # Шанс сохранить в избранное
                        # 5% для длинных (>200 символов), 3% для коротких
                        save_chance = save_probability if text_length > 200 else save_probability_short
                        if not is_skipped and msg_id and text_length > 0 and random.random() < save_chance:
                            try:
                                # Пересылаем в Saved Messages (chat_id = "me")
                                forward_result = await self.telegram_client.invoke_raw(
                                    session_id,
                                    f"pylogram.raw.functions.messages.ForwardMessages("
                                    f"from_peer={resolved_peer['input_peer']!r}, "
                                    f"id=[{msg_id}], "
                                    f"to_peer=pylogram.raw.types.InputPeerSelf(), "
                                    f"random_id=[{random.randint(1, 2**63)}])"
                                )
                                if not forward_result.get("error"):
                                    messages_saved += 1
                                    logger.info(f"  ⭐ Saved msg #{msg_id} to favorites")
                                else:
                                    logger.debug(f"  ⚠️ Could not save: {forward_result.get('error')}")
                            except Exception as e:
                                logger.debug(f"  ⚠️ Save failed: {e}")

                    if messages_read == 0:
                        logger.info(f"📭 No messages found in {chat_username}")
                    else:
                        avg_time = actual_read_time / messages_read if messages_read > 0 else 0
                        logger.info(f"✅ Read {messages_read} messages in {actual_read_time:.1f}s (avg {avg_time:.1f}s/msg)")
                        if reactions_sent > 0:
                            logger.info(f"   💬 Reactions sent: {reactions_sent}")
                        if messages_saved > 0:
                            logger.info(f"   ⭐ Messages saved: {messages_saved}")
                        
                except Exception as exc:
                    logger.error(f"Error parsing messages: {exc}")
                    messages_read = 0
            else:
                error_msg = history_result.get("error", "Unknown error")
                logger.warning(f"⚠️ Could not fetch messages from {chat_username}: {error_msg}")
        else:
            # Нет непрочитанных - просто читаем последние для вида
            # Но всё равно можем реагировать и сохранять!
            logger.info(f"✅ All messages already read in {chat_username}")
            history_result = await self.telegram_client.get_chat_history(session_id, resolved_peer, limit=5)
            
            if not history_result.get("error"):
                try:
                    result_data = history_result.get("result") or {}
                    messages = result_data.get("messages", []) if isinstance(result_data, dict) else []
                    
                    # Параметры engagement для уже прочитанных сообщений
                    react_probability = 0.10  # 10% шанс поставить реакцию
                    save_probability = 0.05   # 5% шанс сохранить длинное
                    save_probability_short = 0.03  # 3% для короткого
                    
                    for msg in messages[:5]:
                        msg_id = msg.get("id")
                        if isinstance(msg_id, int):
                            last_message_id = max(last_message_id, msg_id)
                        msg_text = msg.get("message") or msg.get("text", "")
                        text_length = len(msg_text)
                        
                        if msg_text:
                            messages_texts.append(msg_text[:200])
                            messages_read += 1
                        
                        # Симуляция просмотра: 1-3 секунды на сообщение
                        await asyncio.sleep(random.uniform(1, 3))
                        
                        # === ENGAGEMENT для уже прочитанных сообщений ===
                        
                        # Шанс поставить реакцию
                        if msg_id and random.random() < react_probability:
                            try:
                                msg_reactions = msg.get("reactions", {})
                                available_reactions = []
                                
                                if isinstance(msg_reactions, dict):
                                    results = msg_reactions.get("results", [])
                                    for r in results:
                                        if isinstance(r, dict):
                                            reaction = r.get("reaction", {})
                                            if isinstance(reaction, dict):
                                                emoticon = reaction.get("emoticon")
                                                if emoticon:
                                                    available_reactions.append(emoticon)
                                
                                if available_reactions:
                                    reaction_emoji = random.choice(available_reactions)
                                    react_result = await self.telegram_client.send_reaction(
                                        session_id, chat_username, msg_id, reaction_emoji
                                    )
                                    if not react_result.get("error"):
                                        reactions_sent += 1
                                        logger.info(f"  💬 Reacted with {reaction_emoji} to msg #{msg_id}")
                                    else:
                                        logger.debug(f"  ⚠️ Could not react: {react_result.get('error')}")
                                else:
                                    logger.debug(f"  ℹ️ No reactions available on msg #{msg_id}")
                            except Exception as e:
                                logger.debug(f"  ⚠️ Reaction failed: {e}")
                        
                        # Шанс сохранить в избранное
                        save_chance = save_probability if text_length > 200 else save_probability_short
                        if msg_id and text_length > 0 and random.random() < save_chance:
                            try:
                                forward_result = await self.telegram_client.invoke_raw(
                                    session_id,
                                    f"pylogram.raw.functions.messages.ForwardMessages("
                                    f"from_peer={resolved_peer['input_peer']!r}, "
                                    f"id=[{msg_id}], "
                                    f"to_peer=pylogram.raw.types.InputPeerSelf(), "
                                    f"random_id=[{random.randint(1, 2**63)}])"
                                )
                                if not forward_result.get("error"):
                                    messages_saved += 1
                                    logger.info(f"  ⭐ Saved msg #{msg_id} to favorites")
                                else:
                                    logger.debug(f"  ⚠️ Could not save: {forward_result.get('error')}")
                            except Exception as e:
                                logger.debug(f"  ⚠️ Save failed: {e}")
                    
                    if reactions_sent > 0 or messages_saved > 0:
                        logger.info(f"   📊 Engagement on re-read: {reactions_sent} reactions, {messages_saved} saves")
                        
                except Exception as exc:
                    logger.error(f"Error reading already-read messages: {exc}")

        # mark_history_read уже вызван выше сразу после получения сообщений
        # Это гарантирует что сообщения отмечаются как прочитанные даже если симуляция прервётся

        # По документации Telegram: реклама появляется ПОСЛЕ того как пользователь
        # прокрутил ниже последнего сообщения в канале
        # https://core.telegram.org/api/sponsored-messages
        if should_fetch_ads:
            logger.info("📢 User scrolled past last message - fetching sponsored ads...")
            sponsored_result = await self.telegram_client.get_sponsored_messages(
                session_id,
                chat_username
            )

            if sponsored_result.get("success"):
                result_data = sponsored_result.get("result", {})
                ad_messages = result_data.get("messages", [])

                if ad_messages:
                    logger.info(f"📢 Found {len(ad_messages)} sponsored message(s) for {chat_username}")
                    for idx, ad in enumerate(ad_messages, 1):
                        title = ad.get("title", "")
                        message = ad.get("message", "")
                        url = ad.get("url", "")
                        button_text = ad.get("button_text", "")
                        recommended = ad.get("recommended", False)
                        random_id = ad.get("random_id")

                        logger.info(f"  Ad #{idx}: {title[:50]}..." if len(title) > 50 else f"  Ad #{idx}: {title}")

                        sponsored_ads.append({
                            "title": title,
                            "message": message,
                            "url": url,
                            "button_text": button_text,
                            "recommended": recommended,
                            "random_id": random_id
                        })

                        # Вызываем viewSponsoredMessage когда пользователь "видит" рекламу
                        if random_id:
                            try:
                                await self.telegram_client.view_sponsored_message(session_id, random_id)
                                logger.debug(f"    ✓ Marked ad #{idx} as viewed")
                            except Exception as exc:
                                logger.warning(f"    ⚠ Failed to mark ad as viewed: {exc}")
                else:
                    logger.info(f"📭 No sponsored messages available for {chat_username}")
            elif "AD_EXPIRED" in str(sponsored_result.get("error", "")):
                logger.info(f"⏰ Sponsored messages expired for {chat_username}")
            elif "PREMIUM_ACCOUNT_REQUIRED" in str(sponsored_result.get("error", "")):
                logger.info("💎 Account is actually premium (server says so)")
            else:
                logger.warning(f"⚠ Could not fetch sponsored messages: {sponsored_result.get('error')}")

        response = {
            "action": "read_messages",
            "chat": chat_username,
            "chat_type": chat_type or None,
            "duration": duration,
            "status": "completed",
            "is_premium": is_premium,
            "unread_count_before": unread_count,
            "messages_read": messages_read,
            "messages_preview": messages_texts[:3] if messages_texts else [],
            "reactions_sent": reactions_sent,
            "messages_saved": messages_saved
        }
        response["channel"] = chat_username  # backward compatibility

        if sponsored_ads:
            response["sponsored_ads_count"] = len(sponsored_ads)
            response["sponsored_ads"] = sponsored_ads
        
        # mark_history_read вызывается inline выше при обработке сообщений

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
        """React to a message - DISABLED for channels, only allowed in groups"""
        channel_username = action.get("channel_username") or action.get("chat_username")

        if not channel_username:
            return {"error": "Missing channel_username"}

        # DISABLED: Reactions in channels are too risky
        # Check if this is a channel (not a group)
        account = get_account(session_id)
        if not account:
            logger.error(f"❌ Account not found for session {session_id} - blocking reaction for safety")
            return {
                "action": "react_to_message",
                "channel": channel_username,
                "status": "error",
                "reason": "Account not found in database"
            }

        account_id = account.get("id")
        from database import get_db_connection
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT chat_type FROM discovered_chats WHERE account_id = ? AND chat_username = ?",
                (account_id, channel_username)
            )
            row = cursor.fetchone()
            if row:
                chat_type = row['chat_type']
                if chat_type == 'channel':
                    logger.info(f"🚫 Reactions in CHANNELS disabled - skipping {channel_username}")
                    return {
                        "action": "react_to_message",
                        "channel": channel_username,
                        "status": "skipped",
                        "reason": "Reactions in channels disabled"
                    }

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
        """
        Reply to a message in a chat - DISABLED for public chats.
        Only private bot groups are allowed.
        """
        from database import (
            get_account, update_account, get_persona,
            can_send_message_in_chat, increment_chat_messages_sent,
            is_private_bot_group, save_sent_message, get_account_messages_in_chat
        )

        chat_username = action.get("chat_username")

        if not chat_username:
            return {"error": "Missing chat_username"}

        # DISABLED: reply_in_chat for PUBLIC chats is too risky
        # Only allow private bot groups
        if not is_private_bot_group(chat_username):
            logger.info(f"🚫 reply_in_chat DISABLED for public chat {chat_username}")
            return {
                "action": "reply_in_chat",
                "chat": chat_username,
                "status": "skipped",
                "reason": "reply_in_chat disabled for public chats"
            }

        # Below code only runs for private bot groups
        from chat_context_analyzer import ChatContextAnalyzer
        from admin_api_client import AdminAPIClient

        reply_text = action.get("reply_text", "")
        use_context_analysis = action.get("use_context_analysis", True)

        account = get_account(session_id)
        if not account:
            return {"error": "Account not found"}

        # Check if this is a real public chat (not a private bot group)
        # Only accounts with status=0 in Admin API can write to real public chats
        if not is_private_bot_group(chat_username):
            try:
                admin_api = AdminAPIClient()
                status = await admin_api.check_session_status(session_id)

                if status != 0:
                    logger.info(
                        f"Cannot reply in real chat {chat_username}: "
                        f"session {session_id} has status={status} (need status=0)"
                    )
                    return {
                        "action": "reply_in_chat",
                        "chat": chat_username,
                        "status": "skipped",
                        "reason": f"Account status={status}, only status=0 can write to real public chats"
                    }
            except Exception as e:
                logger.warning(f"Admin API check failed for {session_id}: {e}")
                # Be conservative - don't allow if we can't verify
                return {
                    "action": "reply_in_chat",
                    "chat": chat_username,
                    "status": "skipped",
                    "reason": f"Could not verify account status in Admin API: {e}"
                }

        account_id = account.get("id")

        # Check chat exclusivity for warmup accounts (anti-linking protection)
        # Multiple warmup accounts should NOT send messages to the same chat
        if account.get("account_type") == "warmup":
            from database import is_chat_exclusive_for_warmup
            is_exclusive, existing_id = is_chat_exclusive_for_warmup(account_id, chat_username)
            if not is_exclusive:
                logger.info(
                    f"⚠️ Chat {chat_username} already has warmup account {existing_id} - "
                    f"blocking message from account {account_id} to prevent linking"
                )
                return {
                    "action": "reply_in_chat",
                    "chat": chat_username,
                    "status": "skipped",
                    "reason": f"Chat occupied by another warmup account ({existing_id})"
                }

        # Check daily limit for real chats
        if not can_send_message_in_chat(account_id, chat_username):
            logger.info(f"Daily message limit reached for {chat_username}")
            return {
                "action": "reply_in_chat",
                "chat": chat_username,
                "status": "skipped",
                "reason": "Daily message limit reached"
            }

        # If no reply text provided and context analysis enabled, generate one
        if not reply_text and use_context_analysis:
            logger.info(f"Generating contextual response for {chat_username}...")

            try:
                # Get persona for context
                persona = get_persona(account_id) or {}

                # Get persona's previous messages in this chat (for memory)
                persona_messages = get_account_messages_in_chat(account_id, chat_username, limit=10)
                if persona_messages:
                    logger.info(f"📚 Loaded {len(persona_messages)} previous messages for persona memory")

                # Fetch recent messages
                resolved = await self.telegram_client.resolve_peer(session_id, chat_username)
                if not resolved.get("success"):
                    return {"error": f"Could not resolve chat {chat_username}"}

                history = await self.telegram_client.get_chat_history(
                    session_id=session_id,
                    peer_info=resolved,
                    limit=30
                )

                if history.get("error"):
                    return {"error": f"Could not fetch chat history: {history.get('error')}"}

                # Parse messages
                messages = self._parse_chat_messages(history.get("result", {}))

                if len(messages) < 5:
                    return {
                        "action": "reply_in_chat",
                        "chat": chat_username,
                        "status": "skipped",
                        "reason": "Not enough messages for context"
                    }

                # Analyze context (with persona memory)
                analyzer = ChatContextAnalyzer()
                analysis = await analyzer.analyze_chat_context(
                    messages=messages,
                    persona=persona,
                    persona_messages=persona_messages
                )

                if not analysis.get("should_respond"):
                    logger.info(f"Context analysis: should not respond in {chat_username}")
                    return {
                        "action": "reply_in_chat",
                        "chat": chat_username,
                        "status": "skipped",
                        "reason": analysis.get("reason", "Context analysis declined")
                    }

                # Get response from analysis or generate new
                reply_text = analysis.get("suggested_response")
                if not reply_text:
                    reply_text = await analyzer.generate_contextual_response(
                        messages=messages,
                        persona=persona,
                        topic_hint=analysis.get("topic"),
                        persona_messages=persona_messages
                    )

                if not reply_text:
                    return {
                        "action": "reply_in_chat",
                        "chat": chat_username,
                        "status": "skipped",
                        "reason": "Could not generate contextual response"
                    }

            except Exception as e:
                logger.error(f"Error in context analysis: {e}")
                # Fallback to generic response from behavioral profile
                bp = getattr(self, '_current_profile', None) or DEFAULT_BEHAVIORAL_PROFILE
                fallback_phrases = bp.get("fallback_phrases", DEFAULT_BEHAVIORAL_PROFILE["fallback_phrases"])
                reply_text = random.choice(fallback_phrases)

        # Fallback if still no text
        if not reply_text:
            bp = getattr(self, '_current_profile', None) or DEFAULT_BEHAVIORAL_PROFILE
            fallback_phrases = bp.get("fallback_phrases", DEFAULT_BEHAVIORAL_PROFILE["fallback_phrases"])
            reply_text = random.choice(fallback_phrases)

        logger.info(f"Replying in {chat_username}: {reply_text[:50]}...")

        # Check for spam keywords
        if self._check_floodwait_keywords(reply_text):
            return {"error": "Reply text contains potential spam keywords"}

        try:
            # Simulate typing delay based on message length
            bp = getattr(self, '_current_profile', None) or DEFAULT_BEHAVIORAL_PROFILE
            bp_msg = bp.get("messaging", DEFAULT_BEHAVIORAL_PROFILE["messaging"])
            typing_delay = len(reply_text) * random.uniform(
                bp_msg.get("typing_delay_per_char_min", 0.05),
                bp_msg.get("typing_delay_per_char_max", 0.10)
            )
            typing_delay = min(typing_delay, 45)  # cap at 45 sec
            await asyncio.sleep(typing_delay)

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
                    update_account(session_id, is_frozen=True)
                return result

            # Success - update statistics and save message for audit/memory
            increment_chat_messages_sent(account_id, chat_username)

            # Save message for persona memory and audit
            context_summary = action.get("reason", "")[:200]
            save_sent_message(account_id, chat_username, reply_text, context_summary)
            logger.info(f"💾 Saved message to audit: {chat_username} ({len(reply_text)} chars)")

            return {
                "action": "reply_in_chat",
                "chat": chat_username,
                "status": "sent",
                "message_preview": reply_text[:50],
                "telegram_result": result
            }

        except Exception as e:
            logger.error(f"Error replying in chat: {e}")
            return {"error": str(e)}

    def _parse_chat_messages(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse messages from Telegram API response for context analysis"""
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
            })

        return messages
    
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
        
        # Попробуем взять последнее сообщение из источника
        try:
            src_result = await self.telegram_client.get_channel_messages(
                session_id,
                from_chat,
                limit=1
            )
        except Exception as exc:
            logger.error(f"Error fetching source messages for forward: {exc}")
            return {"error": str(exc)}
        
        src_message_text = None
        if isinstance(src_result, dict) and not src_result.get("error"):
            messages = src_result.get("result") or src_result.get("messages") or src_result.get("data")
            if isinstance(messages, list) and messages:
                msg = messages[0]
                src_message_text = (msg.get("message") or msg.get("text") or "")[:1000]
        
        # Если нет текста, делаем ссылку на источник
        if not src_message_text:
            src_message_text = f"Forwarded from {from_chat}"
        
        try:
            send_result = await self.telegram_client.send_message(
                session_id,
                to_chat,
                src_message_text
            )
        except Exception as exc:
            logger.error(f"Error forwarding message: {exc}")
            return {"error": str(exc)}
        
        if send_result.get("error"):
            return {"error": send_result.get("error"), "success": False}
        
        return {
            "action": "forward_message",
            "from_chat": from_chat,
            "to_chat": to_chat,
            "status": "completed",
            "message_preview": src_message_text[:120]
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

    async def _reply_to_dm(self, session_id: str, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reply to an incoming DM in an existing conversation.

        Args:
            session_id: Session ID of the sender
            action: Action dict with conversation_id and message

        Returns:
            Result dict with success/error status
        """
        from database import (
            get_conversation, get_account, save_conversation_message,
            update_conversation
        )
        from datetime import datetime

        conversation_id = action.get("conversation_id")
        message = action.get("message")

        if not conversation_id or not message:
            return {"error": "Missing conversation_id or message"}

        logger.info(f"📩 Replying to DM in conversation {conversation_id}")

        # Get conversation info
        conversation = get_conversation(conversation_id)
        if not conversation:
            logger.warning(f"Conversation {conversation_id} not found")
            return {"error": f"Conversation {conversation_id} not found"}

        # Determine who we're replying to
        initiator_session = conversation.get("initiator_session_id")
        responder_session = conversation.get("responder_session_id")

        # Find the peer (the other party)
        if str(initiator_session) == str(session_id):
            peer_session_id = responder_session
        else:
            peer_session_id = initiator_session

        if not peer_session_id:
            return {"error": "Could not determine peer session"}

        # Get our account ID for recording the message
        sender_account = get_account(session_id)
        if not sender_account:
            return {"error": f"Could not find account for session {session_id}"}

        sender_account_id = sender_account["id"]

        # Get peer account to find their phone/username
        peer_account = get_account(str(peer_session_id))
        if not peer_account:
            return {"error": f"Could not find peer account {peer_session_id}"}

        # Prefer username, fallback to phone
        peer_identifier = peer_account.get("username") or peer_account.get("phone")
        if not peer_identifier:
            return {"error": "Peer has no username or phone"}

        logger.info(f"📤 Sending reply to {peer_identifier}: {message[:50]}...")

        # Send the message via Telegram
        result = await self.telegram_client.send_message(
            session_id,
            peer_identifier,
            message,
            disable_notification=True
        )

        if result.get("error"):
            logger.error(f"Failed to send DM reply: {result.get('error')}")
            return result

        # Record the message in database
        telegram_message_id = result.get("result", {}).get("message_id")

        msg_id = save_conversation_message(
            conversation_id=conversation_id,
            sender_account_id=sender_account_id,
            message_text=message,
            message_type="text",
            telegram_message_id=telegram_message_id
        )

        if msg_id:
            logger.info(f"✅ Message saved to conversation {conversation_id} (msg_id={msg_id})")

            # Update conversation stats
            current_count = conversation.get("message_count", 0)
            update_conversation(
                conversation_id,
                message_count=current_count + 1,
                last_message_at=datetime.utcnow()
            )
        else:
            logger.warning("Failed to save message to database")

        return {
            "action": "reply_to_dm",
            "conversation_id": conversation_id,
            "peer": peer_identifier,
            "message_preview": message[:50],
            "status": "sent",
            "telegram_message_id": telegram_message_id
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
        """Get a randomized natural delay between actions using behavioral profile"""
        bp = getattr(self, '_current_profile', None) or DEFAULT_BEHAVIORAL_PROFILE
        timing = bp.get("timing", DEFAULT_BEHAVIORAL_PROFILE["timing"])

        min_delay = timing.get("min_action_delay", ACTION_DELAYS["min_between_actions"])
        max_delay = timing.get("max_action_delay", ACTION_DELAYS["max_between_actions"])

        delay = random.uniform(min_delay, max_delay)

        # Add occasional longer pauses
        pause_prob = timing.get("long_pause_probability", 0.1)
        if random.random() < pause_prob:
            extra_min = timing.get("long_pause_extra_min", 5)
            extra_max = timing.get("long_pause_extra_max", 10)
            delay += random.uniform(extra_min, extra_max)
        
        return round(delay, 2)
