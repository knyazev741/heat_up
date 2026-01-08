"""
WarmupScheduler - автоматический планировщик прогрева аккаунтов
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import json
import random

from telegram_client import TelegramAPIClient
from persona_agent import PersonaAgent
from search_agent import SearchAgent
from llm_agent import ActionPlannerAgent
from executor import ActionExecutor
from config import settings
from database import (
    get_accounts_for_warmup,
    get_account,
    get_account_by_id,
    get_persona,
    save_persona,
    get_relevant_chats,
    save_discovered_chat,
    save_warmup_session,
    update_account,
    update_account_stage,
    should_skip_warmup
)
from admin_sync import sync_session_statuses, get_last_sync_time, save_last_sync_time, sync_helper_accounts
from conversation_engine import get_conversation_engine
from group_engine import get_group_engine
from database import count_active_conversations, count_active_bot_groups, count_helper_accounts

logger = logging.getLogger(__name__)


class WarmupScheduler:
    """
    Автоматический планировщик прогрева аккаунтов
    
    Запускает прогрев N раз в день для каждого аккаунта
    в соответствии с их индивидуальными настройками
    """
    
    def __init__(self):
        self.telegram_client = TelegramAPIClient()
        self.persona_agent = PersonaAgent()
        self.search_agent = SearchAgent()
        self.action_planner = ActionPlannerAgent()
        self.executor = ActionExecutor(self.telegram_client)
        self.conversation_engine = get_conversation_engine(self.telegram_client)
        self.group_engine = get_group_engine(self.telegram_client)

        self.is_running = False
        self.started_at = None
        self._task = None

        # Phase 1 settings
        self.enable_private_conversations = True  # Enable Phase 1.2 DM feature
        self.enable_group_chats = True  # Enable Phase 1.3 Group chats feature
    
    async def start(self):
        """Запустить scheduler"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        self.is_running = True
        self.started_at = datetime.utcnow()
        
        logger.info("=" * 100)
        logger.info("🚀 WARMUP SCHEDULER STARTED")
        logger.info("=" * 100)
        logger.info(f"Check interval: {settings.scheduler_check_interval} seconds")
        logger.info(f"Started at: {self.started_at}")
        logger.info("=" * 100)
        
        # Perform initial sync from Admin API if enabled
        if settings.admin_sync_enabled:
            logger.info("🔄 Performing initial Admin API sync...")
            try:
                result = await sync_session_statuses()
                if result['success']:
                    save_last_sync_time()
                    logger.info(
                        f"✅ Initial sync completed: "
                        f"{result['frozen_count']} frozen, "
                        f"{result['deleted_count']} deleted, "
                        f"{result['banned_forever_count']} banned forever"
                    )
                else:
                    logger.warning(f"⚠️ Initial sync failed: {result.get('error', 'Unknown error')}")
            except Exception as e:
                logger.error(f"❌ Error during initial sync: {e}")

            # Sync helper accounts for Phase 1 conversations/groups
            logger.info("🔄 Syncing helper accounts...")
            try:
                helper_result = await sync_helper_accounts()
                if helper_result['success']:
                    logger.info(
                        f"✅ Helper sync completed: "
                        f"{helper_result['added']} added, "
                        f"{helper_result['updated']} updated, "
                        f"{helper_result['skipped']} skipped"
                    )
                else:
                    logger.warning(f"⚠️ Helper sync failed: {helper_result.get('error', 'Unknown error')}")
            except Exception as e:
                logger.error(f"❌ Error syncing helpers: {e}")
        else:
            logger.info("ℹ️ Admin API sync disabled in settings")
        
        self._task = asyncio.create_task(self._run_loop())
    
    async def stop(self):
        """Остановить scheduler"""
        if not self.is_running:
            logger.warning("Scheduler is not running")
            return
        
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("=" * 100)
        logger.info("🛑 WARMUP SCHEDULER STOPPED")
        logger.info("=" * 100)
    
    async def _run_loop(self):
        """Основной цикл scheduler"""
        
        while self.is_running:
            try:
                logger.info("=" * 80)
                logger.info("⏰ SCHEDULER CHECK CYCLE")
                logger.info("=" * 80)
                
                # Check if we need to sync from Admin API
                if settings.admin_sync_enabled:
                    last_sync = get_last_sync_time()
                    sync_interval = timedelta(hours=settings.admin_sync_interval_hours)
                    
                    should_sync = False
                    if last_sync is None:
                        # Never synced, sync now
                        should_sync = True
                        logger.info("🔄 No previous sync found - syncing now...")
                    else:
                        time_since_sync = datetime.utcnow() - last_sync
                        if time_since_sync >= sync_interval:
                            should_sync = True
                            logger.info(
                                f"🔄 Last sync was {time_since_sync.total_seconds()/3600:.1f}h ago "
                                f"(interval: {settings.admin_sync_interval_hours}h) - syncing..."
                            )
                    
                    if should_sync:
                        try:
                            result = await sync_session_statuses()
                            if result['success']:
                                save_last_sync_time()
                                logger.info(
                                    f"✅ Sync completed: {result['frozen_count']} frozen, "
                                    f"{result['deleted_count']} deleted, "
                                    f"{result['banned_forever_count']} banned forever"
                                )
                            else:
                                logger.warning(f"⚠️ Sync failed: {result.get('error', 'Unknown error')}")
                        except Exception as e:
                            logger.error(f"❌ Error during sync: {e}")
                
                # Получить аккаунты для прогрева
                accounts = get_accounts_for_warmup()
                logger.info(f"Found {len(accounts)} active accounts")
                
                for account in accounts:
                    try:
                        # Проверить, нужно ли прогревать этот аккаунт сейчас
                        if await self._should_warmup_now(account):
                            logger.info(f"🔥 Starting warmup for account {account['session_id'][:8]}...")
                            await self.warmup_account(account['id'])
                        else:
                            logger.debug(f"Skipping account {account['session_id'][:8]} - not time yet")
                    
                    except Exception as e:
                        logger.error(f"Error processing account {account.get('session_id', 'unknown')}: {e}")
                        continue
                
                # ========== PHASE 1.2: Private Conversations ==========
                if self.enable_private_conversations:
                    try:
                        await self._process_conversations()
                    except Exception as e:
                        logger.error(f"Error processing conversations: {e}")

                # ========== PHASE 1.3: Group Chats ==========
                if self.enable_group_chats:
                    try:
                        await self._process_groups()
                    except Exception as e:
                        logger.error(f"Error processing groups: {e}")

                logger.info(f"✅ Check cycle completed. Next check in {settings.scheduler_check_interval}s")
                logger.info("=" * 80)

                # Wait until next check
                await asyncio.sleep(settings.scheduler_check_interval)
            
            except asyncio.CancelledError:
                logger.info("Scheduler loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def _should_warmup_now(self, account: Dict[str, Any]) -> bool:
        """
        Определить, нужно ли прогревать аккаунт сейчас
        
        Args:
            account: Словарь с данными аккаунта
            
        Returns:
            True если нужно прогревать
        """
        
        # Проверяем задержку для новых сессий - если нужно ждать, пропускаем
        from database import check_warmup_delay
        should_wait, delay_until = check_warmup_delay(account)
        if should_wait and delay_until:
            wait_hours = (delay_until - datetime.utcnow()).total_seconds() / 3600
            logger.debug(
                f"Account {account['session_id'][:8]} has delay until {delay_until.isoformat()} "
                f"({wait_hours:.2f}h) - skipping"
            )
            return False
        
        last_warmup = account.get("last_warmup_date")
        min_daily = account.get("min_daily_activity", 3)
        max_daily = account.get("max_daily_activity", 6)
        
        # Берем случайное количество активностей из диапазона для этого дня
        import random
        daily_count = random.randint(min_daily, max_daily)
        
        # Если никогда не прогревали - точно нужно
        if not last_warmup:
            logger.info(f"Account {account['session_id'][:8]} never warmed up - scheduling (target: {daily_count} times/day)")
            return True
        
        try:
            last_time = datetime.fromisoformat(last_warmup)
            time_since_last = datetime.utcnow() - last_time
            
            # Рассчитываем минимальный интервал между прогревами
            # Если daily_count = 3, то каждые ~8 часов
            # Если daily_count = 5, то каждые ~5 часов
            hours_between = 24 / daily_count
            min_interval = timedelta(hours=hours_between * 0.8)  # -20% для вариативности
            max_interval = timedelta(hours=hours_between * 1.2)  # +20% для вариативности
            
            # Добавляем случайность
            target_interval = timedelta(
                hours=hours_between + random.uniform(-1, 1)
            )
            
            # Проверяем, прошел ли достаточный интервал
            if time_since_last >= min_interval:
                logger.info(
                    f"Account {account['session_id'][:8]} last warmed up {time_since_last.total_seconds()/3600:.1f}h ago "
                    f"(target: {hours_between:.1f}h) - scheduling"
                )
                return True
            else:
                time_until_next = min_interval - time_since_last
                logger.debug(
                    f"Account {account['session_id'][:8]} warmed up {time_since_last.total_seconds()/3600:.1f}h ago - "
                    f"next in {time_until_next.total_seconds()/3600:.1f}h"
                )
                return False
        
        except Exception as e:
            logger.error(f"Error calculating warmup time: {e}")
            return False
    
    async def warmup_account(self, account_id: int):
        """
        Полный цикл прогрева одного аккаунта
        
        Args:
            account_id: ID аккаунта в базе данных
        """
        
        logger.info("=" * 100)
        logger.info(f"🎯 WARMUP ACCOUNT {account_id}")
        logger.info("=" * 100)
        
        start_time = datetime.utcnow()
        
        try:
            # 1. Получить данные аккаунта
            account = get_account_by_id(account_id)
            if not account:
                logger.error(f"Account {account_id} not found")
                return
            
            session_id = account["session_id"]
            warmup_stage = account.get("warmup_stage", 1)
            
            logger.info(f"Session ID: {session_id}")
            logger.info(f"Warmup Stage: {warmup_stage}")
            logger.info(f"Phone: {account.get('phone_number', 'unknown')}")
            
            # 1.5. Проверить, нужно ли пропустить этот аккаунт (frozen/deleted/banned forever/LLM disabled)
            should_skip, skip_reason = should_skip_warmup(account)
            if should_skip:
                logger.warning(f"⚠️ SKIPPING warmup for session {session_id}: {skip_reason}")
                logger.warning(f"   This session will be excluded from warmup to save LLM tokens")
                logger.info("=" * 100)
                return
            
            # Задержка для новых сессий теперь проверяется в _should_warmup_now(),
            # поэтому здесь она не нужна - такие сессии не попадут в warmup_account
            
            # 2. Проверить/создать личность
            persona = get_persona(account_id)
            if not persona:
                logger.info("📝 No persona found, generating new persona...")
                persona_data = await self.persona_agent.generate_persona(
                    account["phone_number"],
                    account.get("country")
                )
                persona_id = save_persona(account_id, persona_data)
                if persona_id:
                    persona = get_persona(account_id)
                    logger.info(f"✅ Persona created: {persona_data.get('generated_name')}")
                else:
                    logger.error("Failed to save persona")
                    persona = None
            else:
                logger.info(f"✅ Persona loaded: {persona.get('generated_name')}")
            
            # 3. Обновить пул чатов (если нужно)
            relevant_chats = get_relevant_chats(account_id, limit=15)
            
            # Считаем только каналы с ВЫСОКОЙ релевантностью (>= 0.5) как "доступные"
            # Низкорелевантные каналы (< 0.5) не дают пользы для прогрева
            high_relevance_chats = [c for c in relevant_chats if c.get('relevance_score', 0) >= 0.5]
            
            logger.info(f"📊 Chats: {len(relevant_chats)} total, {len(high_relevance_chats)} high relevance (>=0.5)")
            
            # Проверяем когда последний раз искали каналы
            # Время ожидания зависит от количества релевантных каналов:
            # 0 каналов = 1 день, 1-2 = 2 дня, 3-4 = 3 дня, 5+ = 5 дней
            should_search_chats = False
            if len(high_relevance_chats) < 5 and persona:
                # Вычисляем минимальное время ожидания
                if len(high_relevance_chats) == 0:
                    min_days_wait = 1  # Критично мало каналов - искать через 1 день
                elif len(high_relevance_chats) <= 2:
                    min_days_wait = 2  # Мало каналов - искать через 2 дня
                elif len(high_relevance_chats) <= 4:
                    min_days_wait = 3  # Почти достаточно - искать через 3 дня
                else:
                    min_days_wait = 5  # Нормально - стандартные 5 дней
                
                # Проверяем последний discovered_at
                import sqlite3
                
                conn = sqlite3.connect('data/sessions.db')
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT MAX(discovered_at) as last_search
                    FROM discovered_chats
                    WHERE account_id = ?
                """, (account_id,))
                row = cursor.fetchone()
                conn.close()
                
                if row and row[0]:
                    last_search = datetime.fromisoformat(row[0])
                    days_since_search = (datetime.utcnow() - last_search).days
                    
                    if days_since_search >= min_days_wait:
                        logger.info(f"📅 Last search was {days_since_search} days ago (need {min_days_wait} for {len(high_relevance_chats)} rel chats) - will search")
                        should_search_chats = True
                    else:
                        wait_more = min_days_wait - days_since_search
                        logger.info(f"⏳ Last search was {days_since_search} days ago - wait {wait_more} more days (have {len(high_relevance_chats)} rel chats)")
                else:
                    # Никогда не искали - можно искать
                    logger.info("🆕 Never searched for chats - will search now")
                    should_search_chats = True
            
            if should_search_chats:
                logger.info("🔍 Finding relevant chats for persona...")
                try:
                    new_chats = await self.search_agent.find_relevant_chats(
                        persona,
                        limit=settings.search_chats_per_persona
                    )
                    
                    for chat in new_chats:
                        save_discovered_chat(account_id, chat)
                    
                    logger.info(f"✅ Added {len(new_chats)} new chats")
                except Exception as e:
                    logger.error(f"Error finding chats: {e}")
            
            # 4. Сгенерировать план действий
            logger.info("🎬 Generating action plan...")
            actions = await self.action_planner.generate_action_plan(
                session_id,
                account_data=account,
                persona_data=persona
            )
            
            logger.info(f"✅ Generated {len(actions)} actions")
            
            # 5. Выполнить действия
            logger.info("⚡ Executing actions...")
            execution_summary = await self.executor.execute_action_plan(
                session_id,
                actions
            )
            
            # 6. Сохранить результаты
            completed_at = datetime.utcnow()
            duration = (completed_at - start_time).total_seconds()
            
            session_data = {
                "planned_actions_count": len(actions),
                "completed_actions_count": execution_summary.get("successful_actions", 0),
                "failed_actions_count": execution_summary.get("failed_actions", 0),
                "actions_plan": actions,
                "execution_summary": execution_summary,
                "warmup_stage": warmup_stage,
                "started_at": start_time,
                "completed_at": completed_at
            }
            
            save_warmup_session(account_id, session_data)
            
            # 7. Обновить стадию прогрева (если прошел день)
            first_warmup = account.get("first_warmup_date")
            if first_warmup:
                try:
                    first_time = datetime.fromisoformat(first_warmup)
                    days_since_first = (datetime.utcnow() - first_time).days
                    new_stage = min(days_since_first + 1, settings.warmup_max_stage)
                    
                    if new_stage != warmup_stage:
                        update_account_stage(session_id, new_stage)
                        logger.info(f"🎉 Account progressed to stage {new_stage}")
                except Exception as e:
                    logger.error(f"Error updating stage: {e}")
            
            # 8. КРИТИЧЕСКИ ВАЖНО: Обновить last_warmup_date в БД
            update_account(session_id, last_warmup_date=completed_at.isoformat())
            logger.info(f"📅 Updated last_warmup_date: {completed_at.isoformat()}")
            
            logger.info("=" * 100)
            logger.info(f"✅ WARMUP COMPLETED in {duration:.1f}s")
            logger.info(f"   Successful: {execution_summary.get('successful_actions', 0)}/{len(actions)}")
            logger.info(f"   Failed: {execution_summary.get('failed_actions', 0)}/{len(actions)}")
            logger.info("=" * 100)
        
        except Exception as e:
            logger.error(f"❌ Error during warmup: {e}", exc_info=True)
            logger.error("=" * 100)
    
    async def _process_conversations(self):
        """
        Process private conversations between bot accounts (Phase 1).

        - Process pending responses in active conversations
        - Start new conversations for accounts without enough active dialogs
        """
        active_count = count_active_conversations()
        logger.info(f"💬 Processing conversations... ({active_count} active)")

        # 1. Process pending responses
        responses_sent = await self.conversation_engine.process_pending_responses()
        if responses_sent > 0:
            logger.info(f"   Sent {responses_sent} conversation responses")

        # 2. Start new conversations (with some probability to not spam)
        if random.random() < 0.3:  # 30% chance per cycle
            new_convs = await self.conversation_engine.initiate_new_social_activities()
            if new_convs > 0:
                logger.info(f"   Started {new_convs} new conversations")

        logger.info(f"💬 Conversations processed (now {count_active_conversations()} active)")

    async def _process_groups(self):
        """
        Process group chats between bot accounts (Phase 1.3).

        - Process group activities (send messages)
        - Create new groups for accounts without group membership
        """
        active_groups = count_active_bot_groups()
        logger.info(f"👥 Processing groups... ({active_groups} active)")

        # 1. Process group activities
        messages_sent = await self.group_engine.process_group_activities()
        if messages_sent > 0:
            logger.info(f"   Sent {messages_sent} group messages")

        # 2. Create new groups (with some probability to not spam)
        if random.random() < 0.1:  # 10% chance per cycle
            new_groups = await self.group_engine.initiate_new_group_activities()
            if new_groups > 0:
                logger.info(f"   Created {new_groups} new groups")

        logger.info(f"👥 Groups processed (now {count_active_bot_groups()} active)")

    def get_status(self) -> Dict[str, Any]:
        """Получить статус scheduler"""

        accounts = get_accounts_for_warmup()
        active_conversations = count_active_conversations()
        active_groups = count_active_bot_groups()
        helper_count = count_helper_accounts()

        return {
            "is_running": self.is_running,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "accounts_scheduled": len(accounts),
            "helper_accounts": helper_count,
            "active_conversations": active_conversations,
            "active_groups": active_groups,
            "private_conversations_enabled": self.enable_private_conversations,
            "group_chats_enabled": self.enable_group_chats,
            "next_check_in": settings.scheduler_check_interval if self.is_running else None
        }

