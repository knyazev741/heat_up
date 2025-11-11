import logging
import sys
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from config import settings
from telegram_client import TelegramAPIClient
from llm_agent import ActionPlannerAgent
from executor import ActionExecutor
from database import init_database, get_session_history, cleanup_old_history, get_session_summary
from scheduler import WarmupScheduler
from monitoring import WarmupMonitor
from persona_agent import PersonaAgent
from search_agent import SearchAgent
from admin_api_client import AdminAPIClient
from models import (
    AddAccountRequest, UpdateAccountRequest, AccountResponse, 
    AccountDetailResponse, WarmupNowRequest, StatisticsResponse,
    SchedulerStatusResponse, SuccessResponse
)
from database import (
    add_account, get_account, get_account_by_id, get_all_accounts,
    update_account, get_persona, get_relevant_chats, get_warmup_sessions,
    save_persona, save_discovered_chat, wait_for_warmup_delay, check_warmup_delay
)

# Configure logging
# Create logs directory if it doesn't exist
import os
os.makedirs("logs", exist_ok=True)

# Configure root logger
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        # Console output
        logging.StreamHandler(sys.stdout),
        # File output with detailed logs
        logging.FileHandler("logs/heat_up.log", mode='a', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

logger.info("=" * 100)
logger.info("🚀 HEAT UP SERVICE STARTING")
logger.info(f"Log file: logs/heat_up.log")
logger.info("=" * 100)


# Global clients
telegram_client: Optional[TelegramAPIClient] = None
llm_agent: Optional[ActionPlannerAgent] = None
warmup_scheduler: Optional[WarmupScheduler] = None
warmup_monitor: Optional[WarmupMonitor] = None
persona_agent: Optional[PersonaAgent] = None
search_agent: Optional[SearchAgent] = None


async def cleanup_task():
    """Background task to cleanup old session history daily"""
    while True:
        try:
            await asyncio.sleep(86400)  # Run every 24 hours
            logger.info("Running session history cleanup...")
            cleanup_old_history(days=settings.session_history_days)
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the application"""
    global telegram_client, llm_agent, warmup_scheduler, warmup_monitor, persona_agent, search_agent
    
    # Startup
    logger.info("Starting Heat Up service...")
    
    # Initialize database
    init_database()
    
    # Initialize clients
    telegram_client = TelegramAPIClient()
    llm_agent = ActionPlannerAgent()
    warmup_scheduler = WarmupScheduler()
    warmup_monitor = WarmupMonitor()
    persona_agent = PersonaAgent()
    search_agent = SearchAgent()
    
    # Start background cleanup task
    cleanup_task_handle = asyncio.create_task(cleanup_task())
    
    # Auto-start scheduler if enabled
    if settings.scheduler_enabled:
        logger.info("Auto-starting warmup scheduler...")
        await warmup_scheduler.start()
    
    logger.info("Service ready")
    
    yield
    
    # Shutdown
    logger.info("Shutting down service...")
    
    # Stop scheduler
    if warmup_scheduler and warmup_scheduler.is_running:
        await warmup_scheduler.stop()
    
    cleanup_task_handle.cancel()
    if telegram_client:
        await telegram_client.close()
    if search_agent:
        await search_agent.close()
    logger.info("Service stopped")


app = FastAPI(
    title="Heat Up - Telegram Session Warmup Service",
    description="Simulates natural user behavior for new Telegram accounts using LLM-generated actions",
    version="1.0.0",
    lifespan=lifespan
)


class WarmupResponse(BaseModel):
    """Response model for warmup endpoint"""
    session_id: str
    status: str
    message: str
    action_plan: Optional[list] = None
    execution_summary: Optional[Dict[str, Any]] = None


class WarmupRequest(BaseModel):
    """Optional request body for customization"""
    telegram_api_base_url: Optional[str] = None
    telegram_api_key: Optional[str] = None


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Heat Up",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "telegram_client": telegram_client is not None,
        "llm_agent": llm_agent is not None
    }


@app.post("/warmup/{session_id}", response_model=WarmupResponse)
async def warmup_session(
    session_id: str,
    background_tasks: BackgroundTasks,
    request: Optional[WarmupRequest] = None
):
    """
    Warm up a Telegram session by simulating natural new user behavior
    
    This endpoint:
    1. Generates a unique action plan using LLM
    2. Executes the actions (join channels, read messages, idle periods)
    3. Returns immediately with the plan, executes in background
    
    Args:
        session_id: The Telegram session UID to warm up
        request: Optional configuration overrides
        
    Returns:
        WarmupResponse with action plan and execution details
    """
    if not session_id:
        raise HTTPException(status_code=400, detail="Invalid session_id")
    
    logger.info(f"Received warmup request for session: {session_id}")
    
    try:
        # Get account and persona data
        from database import get_account, get_persona, should_skip_warmup
        account_data = get_account(session_id)
        
        # Проверить, нужно ли пропустить эту сессию
        if account_data:
            should_skip, skip_reason = should_skip_warmup(account_data)
            if should_skip:
                logger.warning(f"⚠️ REJECTING warmup request for session {session_id}: {skip_reason}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot warmup session: {skip_reason}. This session is excluded to save LLM tokens."
                )
        
        persona_data = None
        
        if account_data and account_data.get('id'):
            persona_data = get_persona(account_data['id'])
            if persona_data:
                logger.info(f"📋 Using persona for {session_id}: {persona_data.get('generated_name', 'Unknown')}")
            else:
                logger.info(f"⚠️ No persona found for account {account_data.get('id')}")
        else:
            logger.info(f"⚠️ No account data found for session {session_id}")
        
        # Generate action plan with persona
        action_plan = await llm_agent.generate_action_plan(session_id, account_data, persona_data)
        
        logger.info(f"Generated {len(action_plan)} actions for session {session_id}")
        
        # Create executor with custom client if needed
        if request and (request.telegram_api_base_url or request.telegram_api_key):
            custom_client = TelegramAPIClient(
                base_url=request.telegram_api_base_url,
                api_key=request.telegram_api_key
            )
            executor = ActionExecutor(custom_client)
        else:
            executor = ActionExecutor(telegram_client)
        
        # Проверяем задержку для новых сессий (после генерации плана)
        if account_data:
            should_wait, delay_until = check_warmup_delay(account_data)
            if should_wait and delay_until:
                wait_hours = (delay_until - datetime.utcnow()).total_seconds() / 3600
                logger.info(
                    f"⏳ Session {session_id[:8]}... has delay until {delay_until.isoformat()} "
                    f"({wait_hours:.2f} hours). Actions will be executed after delay."
                )
                # Запускаем выполнение в фоне с задержкой
                async def delayed_execution():
                    await wait_for_warmup_delay(account_data)
                    await executor.execute_action_plan(session_id, action_plan)
                
                asyncio.create_task(delayed_execution())
                
                return WarmupResponse(
                    session_id=session_id,
                    status="scheduled",
                    message=f"Warmup scheduled with {len(action_plan)} actions. Will start after delay (until {delay_until.isoformat()})",
                    action_plan=action_plan
                )
        
        # Execute actions in background (без задержки или задержка уже прошла)
        background_tasks.add_task(
            execute_warmup_background,
            session_id,
            action_plan,
            executor
        )
        
        return WarmupResponse(
            session_id=session_id,
            status="started",
            message=f"Warmup initiated with {len(action_plan)} actions",
            action_plan=action_plan
        )
        
    except Exception as e:
        logger.error(f"Error during warmup: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Warmup failed: {str(e)}")


@app.post("/warmup-sync/{session_id}", response_model=WarmupResponse)
async def warmup_session_sync(
    session_id: str,
    request: Optional[WarmupRequest] = None
):
    """
    Warm up a Telegram session synchronously (waits for completion)
    
    This endpoint:
    1. Generates a unique action plan using LLM
    2. Executes the actions and waits for completion
    3. Returns full execution results
    
    Args:
        session_id: The Telegram session UID to warm up
        request: Optional configuration overrides
        
    Returns:
        WarmupResponse with full execution summary
    """
    if not session_id:
        raise HTTPException(status_code=400, detail="Invalid session_id")
    
    logger.info(f"Received sync warmup request for session: {session_id}")
    
    try:
        # Get account and persona data
        from database import get_account, get_persona, should_skip_warmup
        account_data = get_account(session_id)
        
        # Проверить, нужно ли пропустить эту сессию
        if account_data:
            should_skip, skip_reason = should_skip_warmup(account_data)
            if should_skip:
                logger.warning(f"⚠️ REJECTING sync warmup request for session {session_id}: {skip_reason}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot warmup session: {skip_reason}. This session is excluded to save LLM tokens."
                )
            
            # Проверяем задержку для новых сессий
            should_wait, delay_until = check_warmup_delay(account_data)
            if should_wait and delay_until:
                wait_hours = (delay_until - datetime.utcnow()).total_seconds() / 3600
                raise HTTPException(
                    status_code=400,
                    detail=f"Warmup is delayed for this new session. Actions will start after {delay_until.isoformat()} ({wait_hours:.2f} hours). Use async endpoint /warmup/{session_id} to schedule execution."
                )
        
        persona_data = None
        
        if account_data and account_data.get('id'):
            persona_data = get_persona(account_data['id'])
            if persona_data:
                logger.info(f"📋 Using persona for {session_id}: {persona_data.get('generated_name', 'Unknown')}")
            else:
                logger.info(f"⚠️ No persona found for account {account_data.get('id')}")
        else:
            logger.info(f"⚠️ No account data found for session {session_id}")
        
        # Generate action plan with persona
        action_plan = await llm_agent.generate_action_plan(session_id, account_data, persona_data)
        
        logger.info(f"Generated {len(action_plan)} actions for session {session_id}")
        
        # Create executor
        if request and (request.telegram_api_base_url or request.telegram_api_key):
            custom_client = TelegramAPIClient(
                base_url=request.telegram_api_base_url,
                api_key=request.telegram_api_key
            )
            executor = ActionExecutor(custom_client)
        else:
            executor = ActionExecutor(telegram_client)
        
        # Execute actions synchronously
        execution_summary = await executor.execute_action_plan(session_id, action_plan)
        
        return WarmupResponse(
            session_id=session_id,
            status="completed",
            message=f"Warmup completed: {execution_summary['successful_actions']}/{execution_summary['total_actions']} actions successful",
            action_plan=action_plan,
            execution_summary=execution_summary
        )
        
    except Exception as e:
        logger.error(f"Error during sync warmup: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Warmup failed: {str(e)}")


@app.get("/sessions/{session_id}/history")
async def get_session_history_endpoint(session_id: str, days: int = 30):
    """
    Get session history for a specific session
    
    Args:
        session_id: The Telegram session UID
        days: Number of days to look back (default: 30)
        
    Returns:
        Session history and summary
    """
    try:
        history = get_session_history(session_id, days)
        summary = get_session_summary(session_id, days)
        
        return {
            "session_id": session_id,
            "summary": summary,
            "history": history
        }
    except Exception as e:
        logger.error(f"Error retrieving session history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve history: {str(e)}")


async def execute_warmup_background(
    session_id: str,
    action_plan: list,
    executor: ActionExecutor
):
    """Background task for executing warmup actions"""
    try:
        logger.info(f"Starting background execution for session {session_id}")
        
        # Проверяем и ждем задержку для новых сессий перед выполнением действий
        account_data = get_account(session_id)
        if account_data:
            await wait_for_warmup_delay(account_data)
        
        execution_summary = await executor.execute_action_plan(session_id, action_plan)
        logger.info(
            f"Background execution completed for session {session_id}: "
            f"{execution_summary['successful_actions']}/{execution_summary['total_actions']} successful"
        )
    except Exception as e:
        logger.error(f"Error in background execution for session {session_id}: {str(e)}", exc_info=True)


# ========== NEW ENDPOINTS FOR ACCOUNT MANAGEMENT ==========

def normalize_country_name(country: Optional[str]) -> Optional[str]:
    """
    Нормализует название страны (из "russia" в "Russia", "ukraine" в "Ukraine")
    
    Args:
        country: Название страны (может быть в нижнем регистре)
        
    Returns:
        Нормализованное название страны или None
    """
    if not country:
        return None
    
    # Маппинг для нормализации названий стран
    country_mapping = {
        "russia": "Russia",
        "ukraine": "Ukraine",
        "usa": "USA",
        "united states": "USA",
        "germany": "Germany",
        "france": "France",
        "spain": "Spain",
        "italy": "Italy",
        "poland": "Poland",
        "kazakhstan": "Kazakhstan",
        "belarus": "Belarus",
        "uzbekistan": "Uzbekistan",
        "kyrgyzstan": "Kyrgyzstan",
        "tajikistan": "Tajikistan",
        "turkmenistan": "Turkmenistan",
        "armenia": "Armenia",
        "azerbaijan": "Azerbaijan",
        "georgia": "Georgia",
        "moldova": "Moldova",
        "latvia": "Latvia",
        "estonia": "Estonia",
        "lithuania": "Lithuania",
    }
    
    country_lower = country.lower().strip()
    
    # Проверяем точное совпадение
    if country_lower in country_mapping:
        return country_mapping[country_lower]
    
    # Если уже с большой буквы, возвращаем как есть
    if country[0].isupper():
        return country
    
    # Иначе делаем первую букву заглавной
    return country.capitalize()


@app.post("/accounts/add")
async def add_account_endpoint(request: AddAccountRequest):
    """
    Add new account to warmup system
    
    1. Get country from Admin API by session_id
    2. Generate unique persona for this account
    3. Use persona's activity range (min-max daily activities, unless specified manually)
    4. Find relevant chats based on persona
    5. Add account to DB
    
    Args:
        request: AddAccountRequest with session_id, phone_number, etc.
        
    Returns:
        Account information with persona and discovered chats
    """
    try:
        logger.info(f"Adding new account: {request.session_id}")
        
        # 0. БЫСТРАЯ проверка дубликата ДО генерации персоны
        existing = get_account(request.session_id)
        if existing:
            error_msg = (
                f"Session ID '{request.session_id}' already exists in database "
                f"(Account ID: {existing['id']}, Phone: {existing['phone_number']})"
            )
            logger.warning(f"Duplicate session_id: {error_msg}")
            raise HTTPException(status_code=409, detail=error_msg)
        
        # 0.5. Получаем country из Admin API
        country_from_api = None
        try:
            # Пытаемся преобразовать session_id в число
            try:
                session_id_int = int(request.session_id)
            except ValueError:
                logger.warning(f"Session ID '{request.session_id}' is not a number, skipping Admin API lookup")
            else:
                admin_client = AdminAPIClient()
                try:
                    session_data = await admin_client.get_session_by_id(session_id_int)
                    if session_data:
                        country_from_api = session_data.get('country')
                        if country_from_api:
                            country_from_api = normalize_country_name(country_from_api)
                            logger.info(f"Got country from Admin API: '{country_from_api}' (original: '{session_data.get('country')}')")
                        else:
                            logger.info("Country not found in Admin API response")
                    else:
                        logger.info(f"Session {session_id_int} not found in Admin API")
                except Exception as e:
                    logger.warning(f"Failed to get country from Admin API: {e}")
                finally:
                    await admin_client.close()
        except Exception as e:
            logger.warning(f"Error getting country from Admin API: {e}, will use fallback")
        
        # Определяем country: приоритет у country из API, затем request.country, затем None (будет определено по номеру)
        country = country_from_api or request.country
        
        # Generate fake phone number if not provided
        import random
        phone_number = request.phone_number or f"+7{random.randint(9000000000, 9999999999)}"
        
        # 1. Generate persona (только для новых аккаунтов)
        logger.info(f"Step 1: Generating persona... (country: {country})")
        persona_data = await persona_agent.generate_persona(
            phone_number,
            country
        )
        
        # 2. Use activity range from persona if not specified
        min_daily = request.min_daily_activity
        max_daily = request.max_daily_activity
        
        if min_daily is None or max_daily is None:
            min_daily = persona_data.get("min_daily_activity", 3)
            max_daily = persona_data.get("max_daily_activity", 6)
            logger.info(f"Using LLM-generated activity range: {min_daily}-{max_daily} per day")
        else:
            logger.info(f"Using manually specified activity range: {min_daily}-{max_daily} per day")
        
        # 3. Add account to DB
        logger.info("Step 2: Adding account to database...")
        try:
            # Используем country из persona_data (который уже содержит правильное значение из API или fallback)
            account_country = persona_data.get("country") or country or request.country
            account_id = add_account(
                session_id=request.session_id,
                phone_number=phone_number,
                country=account_country,
                min_daily_activity=min_daily,
                max_daily_activity=max_daily,
                provider=request.provider,
                proxy_id=request.proxy_id
            )
        except ValueError as e:
            # Session ID already exists (двойная проверка на случай race condition)
            logger.warning(f"Duplicate session_id during insert: {str(e)}")
            raise HTTPException(status_code=409, detail=str(e))
        
        if not account_id:
            raise HTTPException(status_code=500, detail="Failed to add account")
        
        # 4. Save persona
        logger.info("Step 3: Saving persona...")
        persona_id = save_persona(account_id, persona_data)
        
        # 5. Find relevant chats
        logger.info("Step 4: Finding relevant chats...")
        discovered_chats = await search_agent.find_relevant_chats(
            persona=persona_data,
            limit=settings.search_chats_per_persona
        )
        
        # 6. Save discovered chats
        logger.info(f"Step 5: Saving {len(discovered_chats)} discovered chats...")
        for chat in discovered_chats:
            save_discovered_chat(account_id, chat)
        
        # 7. Get complete account data
        account = get_account_by_id(account_id)
        
        logger.info(f"✅ Account {account_id} added successfully with persona and {len(discovered_chats)} chats")
        
        return SuccessResponse(
            success=True,
            message=f"Account added successfully with ID {account_id}",
            data={
                **account,
                "persona_generated": True,
                "persona_name": persona_data.get("generated_name"),
                "chats_discovered": len(discovered_chats),
                "activity_range": f"{min_daily}-{max_daily}"
            }
        )
    
    except Exception as e:
        logger.error(f"Error adding account: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/accounts")
async def list_accounts_endpoint(skip: int = 0, limit: int = 50, active_only: bool = False):
    """
    List all accounts with pagination
    
    Args:
        skip: Number of records to skip
        limit: Number of records to return
        active_only: Only return active accounts
        
    Returns:
        List of accounts
    """
    try:
        accounts = get_all_accounts(skip=skip, limit=limit, active_only=active_only)
        return {
            "total": len(accounts),
            "skip": skip,
            "limit": limit,
            "accounts": accounts
        }
    except Exception as e:
        logger.error(f"Error listing accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/accounts/{account_id}")
async def get_account_details_endpoint(account_id: int):
    """
    Get detailed information about an account
    
    Args:
        account_id: Account ID
        
    Returns:
        Detailed account information with persona, chats, and recent sessions
    """
    try:
        account = get_account_by_id(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        persona = get_persona(account_id)
        chats = get_relevant_chats(account_id, limit=20)
        sessions = get_warmup_sessions(account_id, limit=10)
        
        return {
            **account,
            "persona": persona,
            "discovered_chats": chats,
            "recent_warmup_sessions": sessions
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting account details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/accounts/{account_id}/generate-persona")
async def generate_persona_endpoint(account_id: int):
    """
    Generate or regenerate persona for an account
    
    Args:
        account_id: Account ID
        
    Returns:
        Generated persona
    """
    try:
        account = get_account_by_id(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        logger.info(f"Generating persona for account {account_id}")
        
        persona_data = await persona_agent.generate_persona(
            account["phone_number"],
            account.get("country")
        )
        
        persona_id = save_persona(account_id, persona_data)
        
        if persona_id:
            return SuccessResponse(
                success=True,
                message="Persona generated successfully",
                data=persona_data
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to save persona")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating persona: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/accounts/{account_id}/refresh-chats")
async def refresh_chats_endpoint(account_id: int):
    """
    Refresh/discover relevant chats for account's persona
    
    Args:
        account_id: Account ID
        
    Returns:
        List of discovered chats
    """
    try:
        account = get_account_by_id(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        persona = get_persona(account_id)
        if not persona:
            raise HTTPException(status_code=400, detail="No persona configured. Generate persona first.")
        
        logger.info(f"Finding relevant chats for account {account_id}")
        
        new_chats = await search_agent.find_relevant_chats(
            persona,
            limit=settings.search_chats_per_persona
        )
        
        for chat in new_chats:
            save_discovered_chat(account_id, chat)
        
        return SuccessResponse(
            success=True,
            message=f"Found {len(new_chats)} relevant chats",
            data={"chats": new_chats}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing chats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/accounts/{account_id}/warmup-now")
async def warmup_account_now_endpoint(account_id: int, request: WarmupNowRequest = WarmupNowRequest()):
    """
    Trigger warmup for an account immediately (outside schedule)
    
    Args:
        account_id: Account ID
        request: WarmupNowRequest with optional force flag
        
    Returns:
        Warmup result
    """
    try:
        account = get_account_by_id(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        logger.info(f"Manual warmup triggered for account {account_id}")
        
        # Run warmup in background
        asyncio.create_task(warmup_scheduler.warmup_account(account_id))
        
        return SuccessResponse(
            success=True,
            message=f"Warmup started for account {account_id}",
            data={"account_id": account_id, "session_id": account["session_id"]}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering warmup: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/accounts/{account_id}/update")
async def update_account_endpoint(account_id: int, request: UpdateAccountRequest):
    """
    Update account settings
    
    Args:
        account_id: Account ID
        request: UpdateAccountRequest with fields to update
        
    Returns:
        Updated account
    """
    try:
        account = get_account_by_id(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Build update dict from request
        update_data = {}
        if request.min_daily_activity is not None:
            update_data["min_daily_activity"] = request.min_daily_activity
        if request.max_daily_activity is not None:
            update_data["max_daily_activity"] = request.max_daily_activity
        if request.is_active is not None:
            update_data["is_active"] = request.is_active
        if request.warmup_stage is not None:
            update_data["warmup_stage"] = request.warmup_stage
        if request.is_frozen is not None:
            update_data["is_frozen"] = request.is_frozen
        if request.is_banned is not None:
            update_data["is_banned"] = request.is_banned
        
        success = update_account(account["session_id"], **update_data)
        
        if success:
            updated_account = get_account_by_id(account_id)
            return SuccessResponse(
                success=True,
                message="Account updated successfully",
                data=updated_account
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to update account")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/accounts/{account_id}")
async def delete_account_endpoint(account_id: int):
    """
    Delete account from warmup system (not from Telegram!)
    
    Args:
        account_id: Account ID
        
    Returns:
        Success response
    """
    try:
        account = get_account_by_id(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Just mark as inactive rather than deleting
        success = update_account(account["session_id"], is_active=False)
        
        if success:
            return SuccessResponse(
                success=True,
                message=f"Account {account_id} deactivated",
                data={"account_id": account_id}
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to deactivate account")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== SCHEDULER ENDPOINTS ==========

@app.post("/scheduler/start")
async def start_scheduler_endpoint():
    """Start the warmup scheduler"""
    try:
        if warmup_scheduler.is_running:
            return SuccessResponse(
                success=False,
                message="Scheduler is already running",
                data=warmup_scheduler.get_status()
            )
        
        await warmup_scheduler.start()
        
        return SuccessResponse(
            success=True,
            message="Scheduler started successfully",
            data=warmup_scheduler.get_status()
        )
    
    except Exception as e:
        logger.error(f"Error starting scheduler: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scheduler/stop")
async def stop_scheduler_endpoint():
    """Stop the warmup scheduler"""
    try:
        if not warmup_scheduler.is_running:
            return SuccessResponse(
                success=False,
                message="Scheduler is not running",
                data=warmup_scheduler.get_status()
            )
        
        await warmup_scheduler.stop()
        
        return SuccessResponse(
            success=True,
            message="Scheduler stopped successfully",
            data=warmup_scheduler.get_status()
        )
    
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scheduler/status")
async def get_scheduler_status_endpoint():
    """Get scheduler status"""
    try:
        status = warmup_scheduler.get_status()
        return status
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== STATISTICS AND MONITORING ==========

@app.get("/statistics")
async def get_statistics_endpoint():
    """
    Get overall statistics
    
    Returns:
        System-wide statistics
    """
    try:
        stats = warmup_monitor.get_statistics_summary()
        return stats
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/statistics/daily")
async def get_daily_report_endpoint():
    """
    Get daily report
    
    Returns:
        Report for last 24 hours
    """
    try:
        report = warmup_monitor.get_daily_report()
        return report
    except Exception as e:
        logger.error(f"Error getting daily report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/accounts/{account_id}/health")
async def check_account_health_endpoint(account_id: int):
    """
    Check account health
    
    Args:
        account_id: Account ID
        
    Returns:
        Health report with score and recommendations
    """
    try:
        health = warmup_monitor.check_account_health(account_id)
        return health
    except Exception as e:
        logger.error(f"Error checking account health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/accounts/{account_id}/refresh-channels")
async def refresh_channels_endpoint(account_id: int):
    """
    Принудительно запустить поиск новых каналов для аккаунта
    
    Args:
        account_id: Account ID
        
    Returns:
        Список новых найденных каналов
    """
    try:
        # Получаем аккаунт и персону
        account = get_account_by_id(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        persona = get_persona(account_id)
        if not persona:
            raise HTTPException(status_code=400, detail="Persona not found. Generate persona first.")
        
        logger.info(f"🔄 Manually refreshing channels for account {account_id} (session: {account['session_id'][:8]}...)")
        
        # Запускаем поиск
        new_chats = await search_agent.find_relevant_chats(
            persona,
            limit=settings.search_chats_per_persona
        )
        
        # Сохраняем в базу
        saved_count = 0
        for chat in new_chats:
            chat_id = save_discovered_chat(account_id, chat)
            if chat_id:
                saved_count += 1
        
        logger.info(f"✅ Saved {saved_count}/{len(new_chats)} new channels")
        
        # Возвращаем обновленный список каналов
        all_chats = get_relevant_chats(account_id, limit=50)
        
        return {
            "success": True,
            "message": f"Found and saved {saved_count} new channels",
            "new_channels_count": saved_count,
            "total_channels_count": len(all_chats),
            "channels": all_chats
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing channels: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/refresh-all-low-channel-accounts")
async def refresh_all_low_channel_accounts_endpoint():
    """
    Принудительно обновить каналы для всех аккаунтов с малым количеством каналов (< 5)
    
    Returns:
        Результаты обновления
    """
    try:
        all_accounts = get_all_accounts()
        
        results = []
        for account in all_accounts:
            account_id = account['id']
            current_chats = get_relevant_chats(account_id, limit=100)
            
            # Обновляем только если < 5 каналов
            if len(current_chats) < 5:
                try:
                    persona = get_persona(account_id)
                    if not persona:
                        logger.warning(f"Account {account_id} has no persona - skipping")
                        results.append({
                            "account_id": account_id,
                            "session_id": account['session_id'][:8],
                            "success": False,
                            "error": "No persona"
                        })
                        continue
                    
                    logger.info(f"🔄 Refreshing channels for account {account_id} ({len(current_chats)} channels)")
                    
                    new_chats = await search_agent.find_relevant_chats(
                        persona,
                        limit=settings.search_chats_per_persona
                    )
                    
                    saved_count = 0
                    for chat in new_chats:
                        chat_id = save_discovered_chat(account_id, chat)
                        if chat_id:
                            saved_count += 1
                    
                    results.append({
                        "account_id": account_id,
                        "session_id": account['session_id'][:8],
                        "success": True,
                        "before_count": len(current_chats),
                        "new_count": saved_count,
                        "after_count": len(get_relevant_chats(account_id, limit=100))
                    })
                    
                    logger.info(f"✅ Account {account_id}: {len(current_chats)} → {saved_count} new → total {len(get_relevant_chats(account_id, limit=100))}")
                    
                except Exception as e:
                    logger.error(f"Error refreshing account {account_id}: {e}")
                    results.append({
                        "account_id": account_id,
                        "session_id": account['session_id'][:8],
                        "success": False,
                        "error": str(e)
                    })
        
        success_count = sum(1 for r in results if r['success'])
        
        return {
            "success": True,
            "message": f"Refreshed {success_count}/{len(results)} accounts",
            "results": results
        }
    
    except Exception as e:
        logger.error(f"Error refreshing all accounts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level=settings.log_level.lower()
    )

