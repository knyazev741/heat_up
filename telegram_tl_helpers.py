"""
Telegram TL (Type Language) helpers for creating raw API requests.
Uses pylogram to create proper TL objects that match the server's Layer.
"""

import pylogram.raw.types
import pylogram.raw.functions.messages
import pylogram.raw.functions.channels
import pylogram.raw.functions.account
import pylogram.raw.functions.users
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


def make_update_profile_query(
    first_name: str = None,
    last_name: str = None,
    about: str = None
) -> str:
    """
    Create UpdateProfile query to update user's profile information
    
    Args:
        first_name: New first name (optional)
        last_name: New last name (optional)
        about: New bio/about text (optional)
        
    Returns:
        String representation of TL query
        
    Note:
        At least one parameter must be provided. Use empty string "" to clear a field.
    """
    raw_method = pylogram.raw.functions.account.UpdateProfile(
        first_name=first_name,
        last_name=last_name,
        about=about
    )
    
    return raw_method_to_string(raw_method)


def make_get_full_user_query() -> str:
    """
    Create GetFullUser query to get current user's full information
    
    Returns:
        String representation of TL query
    """
    # Use InputUserSelf to get current user
    raw_method = pylogram.raw.functions.users.GetFullUser(
        id=pylogram.raw.types.InputUserSelf()
    )
    
    return raw_method_to_string(raw_method)


def make_get_sponsored_messages_query(
    peer: pylogram.raw.base.input_peer.InputPeer
) -> str:
    """
    Create GetSponsoredMessages query to fetch official ads for channel/bot
    
    According to Telegram's custom client guidelines, this must be called
    when opening channels/bots for non-premium users.
    
    Args:
        peer: InputPeer of the channel or bot chat
        
    Returns:
        String representation of TL query
        
    Note:
        Results should be cached for 5 minutes per channel/bot.
        Layer 201: In some versions it's messages.GetSponsoredMessages,
        in others channels.GetSponsoredMessages. Trying channels first.
    """
    try:
        # Try channels.GetSponsoredMessages (more common in newer versions)
        raw_method = pylogram.raw.functions.channels.GetSponsoredMessages(
            channel=peer
        )
    except AttributeError:
        # Fallback to messages.GetSponsoredMessages
        raw_method = pylogram.raw.functions.messages.GetSponsoredMessages(
            peer=peer
        )
    
    return raw_method_to_string(raw_method)


def make_view_sponsored_message_query(random_id: bytes) -> str:
    """
    Create ViewSponsoredMessage query to mark ad as viewed
    
    Should be called when the entire ad text becomes visible on screen.
    
    Args:
        random_id: Random ID from SponsoredMessage
        
    Returns:
        String representation of TL query
    """
    raw_method = pylogram.raw.functions.messages.ViewSponsoredMessage(
        peer=pylogram.raw.types.InputPeerEmpty(),
        random_id=random_id
    )
    
    return raw_method_to_string(raw_method)


def make_click_sponsored_message_query(
    random_id: bytes,
    media: bool = False,
    fullscreen: bool = False
) -> str:
    """
    Create ClickSponsoredMessage query to mark ad as clicked
    
    Args:
        random_id: Random ID from SponsoredMessage
        media: True if clicking on media (photo/video)
        fullscreen: True if video with sound in fullscreen player
        
    Returns:
        String representation of TL query
    """
    raw_method = pylogram.raw.functions.messages.ClickSponsoredMessage(
        peer=pylogram.raw.types.InputPeerEmpty(),
        random_id=random_id,
        media=media,
        fullscreen=fullscreen
    )
    
    return raw_method_to_string(raw_method)

