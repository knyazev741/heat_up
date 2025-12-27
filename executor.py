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

        # Now join the chat
        result = await self.telegram_client.join_chat(session_id, chat_username)

        if not result.get("error"):
            self.joined_channels.add(chat_username)
            logger.info(f"Successfully joined {chat_username}")

            # Update database - mark chat as joined
            try:
                from database import get_account, update_chat_joined
                account = get_account(session_id)
                if account:
                    account_id = account['id']
                    update_chat_joined(account_id, chat_username)
                    logger.info(f"✅ Marked {chat_username} as joined in database")
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

                    # Параметры случайного поведения
                    skip_probability = 0.15 if len(messages_sorted) >= 3 else 0  # 15% быстрое пролистывание
                    react_probability = 0.10  # 10% шанс поставить реакцию (если есть реакции на сообщении)
                    save_probability = 0.05   # 5% шанс сохранить в избранное (длинные сообщения >200)
                    save_probability_short = 0.03  # 3% шанс для коротких сообщений
                    
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
                            # Реальное чтение: 3-6 символов в секунду
                            base_time = 1.0
                            reading_speed = random.uniform(3, 6)
                            reading_time = text_length / reading_speed if text_length > 0 else 0
                            thinking_time = random.uniform(0.5, 2.0)
                            
                            msg_read_time = base_time + reading_time + thinking_time
                            msg_read_time = min(msg_read_time, 5.0)  # Максимум 5 сек на сообщение
                        
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
            logger.info(f"✅ All messages already read in {chat_username}")
            history_result = await self.telegram_client.get_chat_history(session_id, resolved_peer, limit=5)
            
            if not history_result.get("error"):
                try:
                    result_data = history_result.get("result") or {}
                    messages = result_data.get("messages", []) if isinstance(result_data, dict) else []
                    
                    for msg in messages[:3]:
                        msg_id = msg.get("id")
                        if isinstance(msg_id, int):
                            last_message_id = max(last_message_id, msg_id)
                        msg_text = msg.get("message") or msg.get("text", "")
                        if msg_text:
                            messages_texts.append(msg_text[:200])
                            
                    # Минимальное время для вида
                    await asyncio.sleep(random.uniform(2, 5))
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
