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
            
            logger.info(f"[{idx}/{len(actions)}] Executing: {action_type} - {action.get('reason', 'N/A')}")
            
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
                    logger.warning(f"Action failed: {result['error']}")
                else:
                    # Save successful action to database
                    try:
                        save_session_action(
                            session_id=session_id,
                            action_type=action_type,
                            action_data=json.dumps(action)
                        )
                    except Exception as db_error:
                        logger.error(f"Failed to save action to database: {db_error}")
                
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
        
        if action_type == "join_channel":
            return await self._join_channel(session_id, action)
        elif action_type == "read_messages":
            return await self._read_messages(session_id, action)
        elif action_type == "idle":
            return await self._idle(session_id, action)
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
        """Simulate reading messages in a channel"""
        channel_username = action.get("channel_username")
        duration = action.get("duration_seconds", 5)
        
        if not channel_username:
            return {"error": "Missing channel_username"}
        
        # Simulate reading by getting dialogs (browsing)
        # This is a lightweight operation that shows the user is active
        logger.info(f"Reading messages in {channel_username} for {duration}s")
        
        # Get dialogs to simulate activity
        result = await self.telegram_client.get_dialogs(session_id)
        
        # Wait for the specified duration to simulate reading
        await asyncio.sleep(duration)
        
        return {
            "action": "read_messages",
            "channel": channel_username,
            "duration": duration,
            "status": "completed"
        }
    
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

