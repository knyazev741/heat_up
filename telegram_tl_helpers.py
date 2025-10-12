"""
Telegram TL (Type Language) helpers for creating raw API requests.
Uses pylogram to create proper TL objects that match the server's Layer.
"""

import pylogram.raw.types
import pylogram.raw.functions.messages
import pylogram.raw.functions.channels
from pylogram.raw.core import TLObject


def raw_method_to_string(raw_method: TLObject) -> str:
    """Convert pylogram TL object to string representation for API"""
    return repr(raw_method)


def make_get_dialogs_query(
    offset_date: int = 0,
    offset_id: int = 0,
    offset_peer: pylogram.raw.base.input_peer.InputPeer = None,
    limit: int = 20,
    hash: int = 0,
) -> str:
    """
    Create GetDialogs query string for retrieving user's chat list
    
    Args:
        offset_date: Date offset for pagination
        offset_id: Message ID offset for pagination
        offset_peer: Peer to start from (None = InputPeerEmpty)
        limit: Number of dialogs to fetch
        hash: Hash for caching
        
    Returns:
        String representation of TL query
    """
    if offset_peer is None:
        offset_peer = pylogram.raw.types.InputPeerEmpty()

    raw_method = pylogram.raw.functions.messages.GetDialogs(
        offset_date=offset_date,
        offset_id=offset_id,
        offset_peer=offset_peer,
        limit=limit,
        hash=hash,
    )
    
    return raw_method_to_string(raw_method)


def make_join_channel_query(username: str) -> str:
    """
    Create JoinChannel query string for joining a channel by username
    
    Args:
        username: Channel username (with or without @)
        
    Returns:
        String representation of TL query
    """
    # Remove @ if present
    username = username.lstrip('@')
    
    # First need to resolve username to get InputChannel
    # Using ResolveUsername to get the channel info
    raw_method = pylogram.raw.functions.contacts.ResolveUsername(
        username=username
    )
    
    return raw_method_to_string(raw_method)


def make_resolve_username_query(username: str) -> str:
    """
    Create ResolveUsername query to get channel/user info by username
    
    Args:
        username: Username (with or without @)
        
    Returns:
        String representation of TL query
    """
    username = username.lstrip('@')
    
    raw_method = pylogram.raw.functions.contacts.ResolveUsername(
        username=username
    )
    
    return raw_method_to_string(raw_method)


def make_get_messages_query(
    peer: pylogram.raw.base.input_peer.InputPeer,
    ids: list[int]
) -> str:
    """
    Create GetMessages query to fetch specific messages
    
    Args:
        peer: Input peer (channel/chat/user)
        ids: List of message IDs to fetch
        
    Returns:
        String representation of TL query
    """
    raw_method = pylogram.raw.functions.messages.GetMessages(
        id=ids
    )
    
    return raw_method_to_string(raw_method)


def make_get_history_query(
    peer: pylogram.raw.base.input_peer.InputPeer,
    offset_id: int = 0,
    offset_date: int = 0,
    add_offset: int = 0,
    limit: int = 20,
    max_id: int = 0,
    min_id: int = 0,
    hash: int = 0,
) -> str:
    """
    Create GetHistory query to fetch message history from a chat
    
    Args:
        peer: Input peer (channel/chat/user)
        offset_id: Message ID to start from
        offset_date: Date to start from
        add_offset: Additional offset
        limit: Number of messages to fetch
        max_id: Maximum message ID
        min_id: Minimum message ID
        hash: Hash for caching
        
    Returns:
        String representation of TL query
    """
    raw_method = pylogram.raw.functions.messages.GetHistory(
        peer=peer,
        offset_id=offset_id,
        offset_date=offset_date,
        add_offset=add_offset,
        limit=limit,
        max_id=max_id,
        min_id=min_id,
        hash=hash,
    )
    
    return raw_method_to_string(raw_method)


# Commonly used InputPeer helpers
def make_input_peer_empty() -> pylogram.raw.types.InputPeerEmpty:
    """Create empty InputPeer"""
    return pylogram.raw.types.InputPeerEmpty()


def make_input_peer_channel(channel_id: int, access_hash: int) -> pylogram.raw.types.InputPeerChannel:
    """Create InputPeerChannel"""
    return pylogram.raw.types.InputPeerChannel(
        channel_id=channel_id,
        access_hash=access_hash
    )


def make_input_peer_user(user_id: int, access_hash: int) -> pylogram.raw.types.InputPeerUser:
    """Create InputPeerUser"""
    return pylogram.raw.types.InputPeerUser(
        user_id=user_id,
        access_hash=access_hash
    )

