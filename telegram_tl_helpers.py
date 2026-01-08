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


def make_input_peer_chat(chat_id: int) -> pylogram.raw.types.InputPeerChat:
    """Create InputPeerChat"""
    return pylogram.raw.types.InputPeerChat(
        chat_id=chat_id
    )


def make_input_dialog_peer(
    peer: pylogram.raw.base.input_peer.InputPeer
) -> pylogram.raw.types.InputDialogPeer:
    """Wrap InputPeer into InputDialogPeer"""
    return pylogram.raw.types.InputDialogPeer(
        peer=peer
    )


def make_get_peer_dialogs_query(
    peer: pylogram.raw.base.input_peer.InputPeer
) -> str:
    """Create GetPeerDialogs query for a specific peer"""

    dialog_peer = make_input_dialog_peer(peer)
    raw_method = pylogram.raw.functions.messages.GetPeerDialogs(
        peers=[dialog_peer]
    )

    return raw_method_to_string(raw_method)


def make_read_history_query(
    peer: pylogram.raw.base.input_peer.InputPeer,
    max_id: int = 0
) -> str:
    """Create ReadHistory query to mark messages as read up to max_id
    
    Note: For channels/supergroups, uses channels.ReadHistory
          For chats/users, uses messages.ReadHistory
    """

    # Check peer type and use appropriate method
    peer_type = peer.__class__.__name__
    
    if 'Channel' in peer_type:
        # For channels, use channels.ReadHistory with channel parameter
        # Extract channel_id and access_hash from InputPeerChannel
        channel = pylogram.raw.types.InputChannel(
            channel_id=peer.channel_id,
            access_hash=peer.access_hash
        )
        raw_method = pylogram.raw.functions.channels.ReadHistory(
            channel=channel,
            max_id=max_id
        )
    else:
        # For chats/users, use messages.ReadHistory
        raw_method = pylogram.raw.functions.messages.ReadHistory(
            peer=peer,
            max_id=max_id
        )

    return raw_method_to_string(raw_method)


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
    channel: pylogram.raw.types.InputPeerChannel
) -> str:
    """
    Create GetSponsoredMessages query to fetch official ads for channel/bot
    
    According to Telegram's custom client guidelines, this must be called
    when opening channels/bots for non-premium users.
    
    Args:
        channel: InputPeerChannel with channel_id and access_hash
                 Example: InputPeerChannel(channel_id=1453605446, access_hash=-59287541491096514)
        
    Returns:
        String representation of TL query
        
    Note:
        Results should be cached for 5 minutes per channel/bot.
        Uses channels.GetSponsoredMessages (channel parameter).
        Format: pylogram.raw.functions.channels.GetSponsoredMessages(channel=InputPeerChannel(...))
    """
    # Server expects channels.GetSponsoredMessages with channel= parameter
    # Build string representation directly since pylogram 0.12.3 doesn't have this in channels module
    return f"pylogram.raw.functions.channels.GetSponsoredMessages(channel={repr(channel)})"


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
        random_id=random_id,
        media=media,
        fullscreen=fullscreen
    )

    return raw_method_to_string(raw_method)


def make_import_contacts_query(
    phone: str,
    first_name: str,
    last_name: str = ""
) -> str:
    """
    Create ImportContacts query to add a user to contacts by phone number.

    This is needed before sending DMs to users who are not in your contact list,
    as Telegram requires an access_hash to message users.

    Args:
        phone: Phone number with country code (e.g., "+79123456789")
        first_name: First name for the contact
        last_name: Last name for the contact (optional)

    Returns:
        String representation of TL query
    """
    import pylogram.raw.functions.contacts

    contact = pylogram.raw.types.InputPhoneContact(
        client_id=0,  # Unique identifier, we use 0 since we're adding one contact
        phone=phone,
        first_name=first_name,
        last_name=last_name
    )

    raw_method = pylogram.raw.functions.contacts.ImportContacts(
        contacts=[contact]
    )

    return raw_method_to_string(raw_method)


def make_send_message_query(
    peer: pylogram.raw.base.input_peer.InputPeer,
    message: str,
    random_id: int = None,
    silent: bool = True
) -> str:
    """
    Create SendMessage query to send a message to a peer.

    Args:
        peer: Input peer (channel/chat/user with access_hash)
        message: Message text
        random_id: Random ID for message deduplication (auto-generated if None)
        silent: Send message silently (no notification)

    Returns:
        String representation of TL query
    """
    import random as rand

    if random_id is None:
        random_id = rand.randint(1, 2**63 - 1)

    raw_method = pylogram.raw.functions.messages.SendMessage(
        peer=peer,
        message=message,
        random_id=random_id,
        silent=silent
    )

    return raw_method_to_string(raw_method)

