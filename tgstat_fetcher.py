#!/usr/bin/env python3
"""
TGStat API Channel Fetcher

Fetches real Telegram channels from TGStat API and saves them locally.
Should be run manually when channel list needs updating.
"""

import httpx
import json
import logging
from typing import List, Dict, Any
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TGSTAT_API_TOKEN = "2539dfbdf80afd5c45d0c8f86cc9d21a"
TGSTAT_BASE_URL = "https://api.tgstat.ru"
OUTPUT_FILE = "channels_data.json"

# Categories and search queries to get diverse channels
SEARCH_QUERIES = [
    {"q": "технологии", "category": "Technology"},
    {"q": "новости", "category": "News"},
    {"q": "криптовалюта", "category": "Crypto"},
    {"q": "программирование", "category": "Programming"},
    {"q": "бизнес", "category": "Business"},
    {"q": "наука", "category": "Science"},
    {"q": "развлечения", "category": "Entertainment"},
    {"q": "спорт", "category": "Sports"},
    {"q": "музыка", "category": "Music"},
    {"q": "кино", "category": "Movies"},
]


async def fetch_channels_by_query(
    query: str, 
    category: str, 
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Fetch channels from TGStat API by search query
    
    Args:
        query: Search query
        category: Category name for classification
        limit: Number of channels to fetch
        
    Returns:
        List of channel data
    """
    url = f"{TGSTAT_BASE_URL}/channels/search"
    params = {
        "token": TGSTAT_API_TOKEN,
        "q": query,
        "limit": limit,
        "extended": 1  # Get extended info
    }
    
    logger.info(f"Fetching channels for query: {query} (category: {category})")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "ok":
                channels = data.get("response", {}).get("items", [])
                logger.info(f"Found {len(channels)} channels for query: {query}")
                
                # Format channels
                formatted_channels = []
                for ch in channels:
                    formatted_channels.append({
                        "username": f"@{ch.get('username', ch.get('link', '').replace('https://t.me/', ''))}",
                        "description": ch.get("title", ""),
                        "category": category,
                        "subscribers": ch.get("subscribers_count", 0),
                        "tgstat_url": ch.get("link", "")
                    })
                
                return formatted_channels
            else:
                logger.error(f"API returned error: {data.get('error', 'Unknown error')}")
                return []
                
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching channels for '{query}': {e}")
        return []
    except Exception as e:
        logger.error(f"Error fetching channels for '{query}': {e}")
        return []


async def fetch_all_channels() -> List[Dict[str, Any]]:
    """
    Fetch channels from all search queries
    
    Returns:
        Combined list of all channels
    """
    all_channels = []
    seen_usernames = set()
    
    for search in SEARCH_QUERIES:
        channels = await fetch_channels_by_query(
            query=search["q"],
            category=search["category"],
            limit=20
        )
        
        # Deduplicate by username
        for channel in channels:
            username = channel["username"].lower()
            if username not in seen_usernames:
                seen_usernames.add(username)
                all_channels.append(channel)
        
        # Respect API rate limits - small delay between requests
        import asyncio
        await asyncio.sleep(1)
    
    logger.info(f"Total unique channels fetched: {len(all_channels)}")
    return all_channels


def save_channels_to_file(channels: List[Dict[str, Any]], filepath: str = OUTPUT_FILE):
    """
    Save channels to JSON file
    
    Args:
        channels: List of channel data
        filepath: Output file path
    """
    output_path = Path(filepath)
    
    with output_path.open('w', encoding='utf-8') as f:
        json.dump(channels, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Saved {len(channels)} channels to {filepath}")


async def main():
    """Main function to fetch and save channels"""
    logger.info("Starting TGStat channel fetcher...")
    logger.info(f"API Token: {TGSTAT_API_TOKEN[:20]}...")
    
    try:
        # Fetch channels
        channels = await fetch_all_channels()
        
        if not channels:
            logger.warning("No channels were fetched!")
            return
        
        # Save to file
        save_channels_to_file(channels)
        
        # Print summary
        logger.info("\n" + "="*50)
        logger.info("SUMMARY")
        logger.info("="*50)
        logger.info(f"Total channels: {len(channels)}")
        
        # Count by category
        from collections import Counter
        category_counts = Counter(ch["category"] for ch in channels)
        logger.info("\nChannels by category:")
        for category, count in category_counts.most_common():
            logger.info(f"  {category}: {count}")
        
        logger.info("\nSample channels:")
        for channel in channels[:5]:
            logger.info(f"  {channel['username']} - {channel['description'][:50]}...")
        
        logger.info(f"\nChannels saved to: {OUTPUT_FILE}")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

