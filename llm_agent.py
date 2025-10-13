import json
import logging
from typing import List, Dict, Any
from datetime import datetime
from openai import OpenAI
from config import settings, CHANNEL_POOL
from database import get_session_summary

logger = logging.getLogger(__name__)


class ActionPlannerAgent:
    """LLM-powered agent that generates natural user behavior sequences"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o-mini"
        
    def _build_prompt(self, session_id: str) -> str:
        """
        Build the system prompt for action generation based on session history
        
        Args:
            session_id: Telegram session UID
            
        Returns:
            System prompt string
        """
        
        channels_list = "\n".join([
            f"- {ch['username']}: {ch['description']}" 
            for ch in CHANNEL_POOL
        ])
        
        # Get session history summary
        summary = get_session_summary(session_id, days=settings.session_history_days)
        
        if summary["is_new"]:
            # New user prompt
            user_context = "You are simulating natural behavior for a new Telegram user who just logged in for the first time."
            behavior_note = "This is your first time using Telegram, so explore channels that interest you naturally."
        else:
            # Returning user prompt
            last_activity = summary.get("last_activity")
            if last_activity:
                try:
                    last_time = datetime.fromisoformat(last_activity)
                    time_diff = datetime.utcnow() - last_time
                    if time_diff.days > 0:
                        time_ago = f"{time_diff.days} day{'s' if time_diff.days > 1 else ''} ago"
                    elif time_diff.seconds > 3600:
                        hours = time_diff.seconds // 3600
                        time_ago = f"{hours} hour{'s' if hours > 1 else ''} ago"
                    else:
                        minutes = time_diff.seconds // 60
                        time_ago = f"{minutes} minute{'s' if minutes > 1 else ''} ago"
                except:
                    time_ago = "recently"
            else:
                time_ago = "some time ago"
            
            joined_channels_str = ", ".join(summary["joined_channels"][:10]) if summary["joined_channels"] else "none"
            
            user_context = f"""You are simulating a returning Telegram user who is coming back online.

Previous activity summary:
- Last active: {time_ago}
- Total previous actions: {summary['total_actions']}
- Previously joined channels: {joined_channels_str}

You're back for another session and should continue natural, varied behavior."""
            
            behavior_note = "As a returning user, you can explore new channels, revisit ones you've joined, or just browse. Be natural and diverse."
        
        return f"""{user_context}

Your task is to generate a realistic sequence of 3-7 actions. Be diverse and natural.

Available channels to choose from:
{channels_list}

Available action types:
1. "join_channel" - Join a channel (requires: channel_username)
2. "read_messages" - Browse/read messages in a channel (requires: channel_username, duration_seconds)
3. "idle" - Take a break, simulate being idle (requires: duration_seconds)

Important guidelines:
- {behavior_note}
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
        Generate a natural sequence of actions based on session history
        
        Args:
            session_id: The Telegram session ID (for logging/context)
            
        Returns:
            List of actions to perform
        """
        logger.info(f"Generating action plan for session {session_id}")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=2048,
                temperature=1.0,  # High temperature for diversity
                messages=[
                    {
                        "role": "system",
                        "content": self._build_prompt(session_id)
                    },
                    {
                        "role": "user",
                        "content": f"Generate a natural action sequence for this Telegram user (session: {session_id[:8]}...). Make it unique and realistic!"
                    }
                ]
            )
            
            # Extract JSON from response
            response_text = response.choices[0].message.content
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

