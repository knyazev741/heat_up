import json
import logging
from typing import List, Dict, Any
from anthropic import Anthropic
from config import settings, CHANNEL_POOL

logger = logging.getLogger(__name__)


class ActionPlannerAgent:
    """LLM-powered agent that generates natural user behavior sequences"""
    
    def __init__(self):
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-3-5-sonnet-20241022"
        
    def _build_prompt(self) -> str:
        """Build the system prompt for action generation"""
        
        channels_list = "\n".join([
            f"- {ch['username']}: {ch['description']}" 
            for ch in CHANNEL_POOL
        ])
        
        return f"""You are simulating natural behavior for a new Telegram user who just logged in for the first time.

Your task is to generate a realistic sequence of 3-7 actions that this new user would perform. Be diverse and natural.

Available channels to choose from:
{channels_list}

Available action types:
1. "join_channel" - Join a channel (requires: channel_username)
2. "read_messages" - Browse/read messages in a channel (requires: channel_username, duration_seconds)
3. "idle" - Take a break, simulate being idle (requires: duration_seconds)

Important guidelines:
- Choose 2-4 channels to join based on varied interests
- After joining a channel, often read messages there
- Include idle periods to simulate natural pauses
- Vary the timing - some quick actions, some longer
- Be realistic: don't join too many channels at once
- Mix different types of channels (news, tech, entertainment, etc.)
- Keep total actions between 3-7

Respond with a JSON array of actions. Example format:
[
  {{"action": "join_channel", "channel_username": "@durov", "reason": "Interested in Telegram founder's updates"}},
  {{"action": "read_messages", "channel_username": "@durov", "duration_seconds": 8, "reason": "Reading recent posts"}},
  {{"action": "idle", "duration_seconds": 5, "reason": "Taking a short break"}},
  {{"action": "join_channel", "channel_username": "@tech", "reason": "Interested in technology news"}},
  {{"action": "read_messages", "channel_username": "@tech", "duration_seconds": 12, "reason": "Browsing tech articles"}}
]

Generate a unique, natural sequence each time. Be creative but realistic!"""

    async def generate_action_plan(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Generate a natural sequence of actions for a new user
        
        Args:
            session_id: The Telegram session ID (for logging/context)
            
        Returns:
            List of actions to perform
        """
        logger.info(f"Generating action plan for session {session_id}")
        
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                temperature=1.0,  # High temperature for diversity
                system=self._build_prompt(),
                messages=[
                    {
                        "role": "user",
                        "content": f"Generate a natural action sequence for a new Telegram user (session: {session_id[:8]}...). Make it unique and realistic!"
                    }
                ]
            )
            
            # Extract JSON from response
            response_text = message.content[0].text
            logger.debug(f"LLM response: {response_text}")
            
            # Parse JSON (handle potential markdown code blocks)
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = response_text.strip()
            
            actions = json.loads(json_str)
            
            # Validate actions
            validated_actions = self._validate_actions(actions)
            
            logger.info(f"Generated {len(validated_actions)} actions for session {session_id}")
            return validated_actions
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            # Return fallback actions
            return self._get_fallback_actions()
        except Exception as e:
            logger.error(f"Error generating action plan: {e}")
            return self._get_fallback_actions()
    
    def _validate_actions(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate and sanitize actions from LLM"""
        validated = []
        
        valid_actions = {"join_channel", "read_messages", "idle"}
        
        for action in actions:
            if not isinstance(action, dict):
                continue
                
            action_type = action.get("action")
            if action_type not in valid_actions:
                continue
            
            # Validate required fields
            if action_type == "join_channel":
                if "channel_username" in action:
                    validated.append(action)
            elif action_type == "read_messages":
                if "channel_username" in action and "duration_seconds" in action:
                    # Cap duration at reasonable limits
                    action["duration_seconds"] = min(30, max(3, action["duration_seconds"]))
                    validated.append(action)
            elif action_type == "idle":
                if "duration_seconds" in action:
                    # Cap idle time
                    action["duration_seconds"] = min(15, max(2, action["duration_seconds"]))
                    validated.append(action)
        
        # Ensure we have at least some actions
        if len(validated) < 2:
            logger.warning("Too few valid actions, using fallback")
            return self._get_fallback_actions()
        
        return validated
    
    def _get_fallback_actions(self) -> List[Dict[str, Any]]:
        """Return a safe fallback sequence if LLM fails"""
        return [
            {
                "action": "join_channel",
                "channel_username": "@telegram",
                "reason": "Join official Telegram channel"
            },
            {
                "action": "read_messages",
                "channel_username": "@telegram",
                "duration_seconds": 8,
                "reason": "Browse official updates"
            },
            {
                "action": "idle",
                "duration_seconds": 5,
                "reason": "Short break"
            },
            {
                "action": "join_channel",
                "channel_username": "@durov",
                "reason": "Join Pavel Durov's channel"
            },
            {
                "action": "read_messages",
                "channel_username": "@durov",
                "duration_seconds": 10,
                "reason": "Read posts"
            }
        ]

