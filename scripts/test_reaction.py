#!/usr/bin/env python3
"""
Test script to verify reaction mechanism works.
Uses the same TelegramClient as production to:
1. Get last message from @RVvoenkor
2. Extract available reactions
3. Send a test reaction
"""
import asyncio
import sys
sys.path.insert(0, '/root/heat_up')

from telegram_client import TelegramAPIClient
import random

async def main():
    client = TelegramAPIClient()
    session_id = "27161"
    chat_username = "@RVvoenkor"
    
    print(f"=== Testing Reaction Mechanism ===")
    print(f"Session: {session_id}")
    print(f"Chat: {chat_username}")
    print()
    
    # Step 1: Resolve peer
    print("1. Resolving peer...")
    resolved = await client.resolve_peer(session_id, chat_username)
    if not resolved.get("success"):
        print(f"   ❌ Failed: {resolved.get('error')}")
        return
    print(f"   ✅ Resolved: {resolved.get('peer_type')}")
    
    # Step 2: Get chat history (last 3 messages)
    print("\n2. Getting last 3 messages...")
    history = await client.get_chat_history(session_id, resolved, limit=3)
    if history.get("error"):
        print(f"   ❌ Failed: {history.get('error')}")
        return
    
    result = history.get("result", {})
    messages = result.get("messages", [])
    print(f"   ✅ Got {len(messages)} messages")
    
    # Step 3: Find message with reactions
    print("\n3. Looking for messages with reactions...")
    msg_with_reactions = None
    available_reactions = []
    
    for msg in messages:
        msg_id = msg.get("id")
        msg_text = (msg.get("message") or msg.get("text", ""))[:50]
        reactions = msg.get("reactions", {})
        
        print(f"\n   Msg #{msg_id}: {msg_text}...")
        print(f"   Raw reactions: {reactions}")
        
        if isinstance(reactions, dict):
            results = reactions.get("results", [])
            for r in results:
                if isinstance(r, dict):
                    reaction = r.get("reaction", {})
                    if isinstance(reaction, dict):
                        emoticon = reaction.get("emoticon")
                        if emoticon:
                            # Skip paid stars
                            if emoticon not in ["⭐", "💫"]:
                                available_reactions.append(emoticon)
            
            if available_reactions and not msg_with_reactions:
                msg_with_reactions = msg_id
    
    if not available_reactions:
        print("\n   ⚠️ No available reactions found on any message!")
        print("   This means posts don't have reactions enabled or no one reacted yet")
        return
    
    print(f"\n   ✅ Available reactions: {list(set(available_reactions))}")
    
    # Step 4: Try to send a reaction
    reaction_to_send = random.choice(list(set(available_reactions)))
    print(f"\n4. Sending reaction '{reaction_to_send}' to msg #{msg_with_reactions}...")
    
    result = await client.send_reaction(session_id, chat_username, msg_with_reactions, reaction_to_send)
    
    if result.get("error"):
        print(f"   ❌ Failed: {result.get('error')}")
    else:
        print(f"   ✅ Success! Reaction sent!")
        print(f"   Result: {result}")

if __name__ == "__main__":
    asyncio.run(main())
