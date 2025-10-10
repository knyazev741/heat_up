import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any

from config import settings
from telegram_client import TelegramAPIClient
from llm_agent import ActionPlannerAgent
from executor import ActionExecutor

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


# Global clients
telegram_client: Optional[TelegramAPIClient] = None
llm_agent: Optional[ActionPlannerAgent] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the application"""
    global telegram_client, llm_agent
    
    # Startup
    logger.info("Starting Heat Up service...")
    telegram_client = TelegramAPIClient()
    llm_agent = ActionPlannerAgent()
    logger.info("Service ready")
    
    yield
    
    # Shutdown
    logger.info("Shutting down service...")
    if telegram_client:
        await telegram_client.close()
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
    if not session_id or len(session_id) < 8:
        raise HTTPException(status_code=400, detail="Invalid session_id")
    
    logger.info(f"Received warmup request for session: {session_id}")
    
    try:
        # Generate action plan
        action_plan = await llm_agent.generate_action_plan(session_id)
        
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
        
        # Execute actions in background
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
    if not session_id or len(session_id) < 8:
        raise HTTPException(status_code=400, detail="Invalid session_id")
    
    logger.info(f"Received sync warmup request for session: {session_id}")
    
    try:
        # Generate action plan
        action_plan = await llm_agent.generate_action_plan(session_id)
        
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


async def execute_warmup_background(
    session_id: str,
    action_plan: list,
    executor: ActionExecutor
):
    """Background task for executing warmup actions"""
    try:
        logger.info(f"Starting background execution for session {session_id}")
        execution_summary = await executor.execute_action_plan(session_id, action_plan)
        logger.info(
            f"Background execution completed for session {session_id}: "
            f"{execution_summary['successful_actions']}/{execution_summary['total_actions']} successful"
        )
    except Exception as e:
        logger.error(f"Error in background execution for session {session_id}: {str(e)}", exc_info=True)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level=settings.log_level.lower()
    )

