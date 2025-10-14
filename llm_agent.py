import json
import logging
from typing import List, Dict, Any
from datetime import datetime
from openai import OpenAI
from config import settings, CHANNEL_POOL, BOTS_POOL
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
        
        bots_list = "\n".join([
            f"- {bot['username']}: {bot['description']}" 
            for bot in BOTS_POOL
        ]) if BOTS_POOL else "No bots available"
        
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

Your task is to generate a realistic sequence of 5-12 actions that simulate natural human behavior on Telegram.
BE CREATIVE and DIVERSE - each user should behave uniquely! Don't follow predictable patterns.

Available channels to interact with:
{channels_list}

Available bots to try:
{bots_list}

Available action types (use variety!):

BASIC ACTIONS:
1. "join_channel" - Join a channel
   - Params: channel_username
   
2. "read_messages" - Browse and read messages in a channel
   - Params: channel_username, duration_seconds (3-20)
   
3. "idle" - Take a natural pause/break
   - Params: duration_seconds (2-10)

ENGAGEMENT ACTIONS:
4. "react_to_message" - React to a message with emoji (shows you're engaged!)
   - Params: channel_username
   - Note: System will automatically pick an emoji that's already used in the channel (safe and natural)
   
5. "message_bot" - Send a message to a bot (explore bot features)
   - Params: bot_username, message (e.g., "/start", "/help", "hello")
   
6. "view_profile" - View a channel's profile/info
   - Params: channel_username, duration_seconds (3-8)

IMPORTANT - BE NATURAL AND DIVERSE:
- {behavior_note}
- DON'T always join → read → idle in a loop! Mix it up!
- React to interesting posts (10-30% of reads should have reactions)
- Try messaging 1-2 bots per session (explore features)
- Sometimes view profiles before joining
- Include realistic pauses between different activities
- Show personality - some users are more active, some more passive
- Total actions: 5-12 (more experienced users do more)

Example of DIVERSE behavior:
[
  {{"action": "view_profile", "channel_username": "@telegram", "duration_seconds": 5, "reason": "Checking out the official channel"}},
  {{"action": "join_channel", "channel_username": "@telegram", "reason": "Looks interesting, joining"}},
  {{"action": "read_messages", "channel_username": "@telegram", "duration_seconds": 10, "reason": "Reading latest updates"}},
  {{"action": "react_to_message", "channel_username": "@telegram", "reason": "Liked the update about new features"}},
  {{"action": "idle", "duration_seconds": 4, "reason": "Quick break"}},
  {{"action": "message_bot", "bot_username": "@wiki", "message": "/start", "reason": "Curious about Wikipedia bot"}},
  {{"action": "idle", "duration_seconds": 6, "reason": "Reading bot response"}},
  {{"action": "join_channel", "channel_username": "@crypto", "reason": "Interested in crypto news"}},
  {{"action": "read_messages", "channel_username": "@crypto", "duration_seconds": 15, "reason": "Checking market updates"}},
  {{"action": "react_to_message", "channel_username": "@crypto", "reason": "Exciting news about Bitcoin"}},
  {{"action": "message_bot", "bot_username": "@gif", "message": "cats", "reason": "Looking for funny cat GIFs"}},
  {{"action": "idle", "duration_seconds": 8, "reason": "Taking a longer break"}}
]

Generate a UNIQUE, NATURAL sequence. Make each user's behavior different!"""

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
            # Build prompts
            system_prompt = self._build_prompt(session_id)
            user_prompt = f"Generate a natural action sequence for this Telegram user (session: {session_id[:8]}...). Make it unique and realistic!"
            
            # Log the full conversation being sent to LLM
            logger.info("=" * 100)
            logger.info("📤 SENDING TO LLM (GPT-4o-mini)")
            logger.info("=" * 100)
            logger.info(f"SYSTEM PROMPT:\n{system_prompt}")
            logger.info("-" * 100)
            logger.info(f"USER PROMPT:\n{user_prompt}")
            logger.info("=" * 100)
            
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=2048,
                temperature=1.0,  # High temperature for diversity
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ]
            )
            
            # Extract JSON from response
            response_text = response.choices[0].message.content
            
            # Log the full LLM response
            logger.info("=" * 100)
            logger.info("📥 RECEIVED FROM LLM")
            logger.info("=" * 100)
            logger.info(f"RAW RESPONSE:\n{response_text}")
            logger.info("=" * 100)
            
            # Parse JSON (handle potential markdown code blocks)
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
                logger.info("Extracted JSON from markdown code block (```json)")
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0].strip()
                logger.info("Extracted JSON from markdown code block (```)")
            else:
                json_str = response_text.strip()
                logger.info("Using raw response as JSON")
            
            actions = json.loads(json_str)
            logger.info(f"✅ Successfully parsed {len(actions)} actions from JSON")
            
            # Validate actions
            validated_actions = self._validate_actions(actions)
            
            logger.info("=" * 100)
            logger.info(f"✅ VALIDATION COMPLETE: {len(validated_actions)} / {len(actions)} actions passed")
            logger.info("=" * 100)
            for idx, action in enumerate(validated_actions, 1):
                logger.info(f"  {idx}. [{action.get('action')}] {action.get('reason', 'No reason')[:60]}")
            logger.info("=" * 100)
            
            return validated_actions
            
        except json.JSONDecodeError as e:
            logger.error("=" * 100)
            logger.error(f"❌ JSON PARSE ERROR: {e}")
            logger.error(f"Failed to parse: {response_text[:500] if 'response_text' in locals() else 'No response'}")
            logger.error("=" * 100)
            return self._get_fallback_actions()
        except Exception as e:
            logger.error("=" * 100)
            logger.error(f"❌ ERROR GENERATING ACTION PLAN: {e}")
            logger.error("=" * 100)
            return self._get_fallback_actions()
    
    def _validate_actions(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate and sanitize actions from LLM"""
        validated = []
        
        valid_actions = {
            "join_channel", "read_messages", "idle",
            "react_to_message", "message_bot", "view_profile"
        }
        
        for action in actions:
            if not isinstance(action, dict):
                continue
                
            action_type = action.get("action")
            if action_type not in valid_actions:
                logger.warning(f"Unknown action type: {action_type}, skipping")
                continue
            
            # Validate required fields
            if action_type == "join_channel":
                if "channel_username" in action:
                    validated.append(action)
                    
            elif action_type == "read_messages":
                if "channel_username" in action and "duration_seconds" in action:
                    # Cap duration at reasonable limits
                    action["duration_seconds"] = min(20, max(3, action["duration_seconds"]))
                    validated.append(action)
                    
            elif action_type == "idle":
                if "duration_seconds" in action:
                    # Cap idle time
                    action["duration_seconds"] = min(10, max(2, action["duration_seconds"]))
                    validated.append(action)
                    
            elif action_type == "react_to_message":
                if "channel_username" in action:
                    # Emoji is optional - system will pick one automatically
                    # Remove emoji if LLM provided it (we don't use it anymore)
                    if "emoji" in action:
                        del action["emoji"]
                    validated.append(action)
                        
            elif action_type == "message_bot":
                if "bot_username" in action and "message" in action:
                    # Sanitize message length
                    action["message"] = action["message"][:200]  # Max 200 chars
                    validated.append(action)
                    
            elif action_type == "view_profile":
                if "channel_username" in action:
                    # Add duration if missing
                    if "duration_seconds" not in action:
                        action["duration_seconds"] = 5
                    action["duration_seconds"] = min(8, max(3, action["duration_seconds"]))
                    validated.append(action)
        
        # Ensure we have at least some actions
        if len(validated) < 3:
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

