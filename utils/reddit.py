# app/utils/reddit.py - Updated to include affiliate links

import asyncio
import re
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import praw
from prawcore import RequestException
from urllib.parse import urlparse
from dotenv import load_dotenv

from database.database import Item, PriceHistory, RetailerLink
from utils.price_tracker import check_price_for_link
from utils.affiliate import generate_affiliate_link

# Load environment variables
load_dotenv()

# Configure Reddit API client
reddit_client = praw.Reddit(
    client_id=os.getenv('REDDIT_CLIENT_ID'),
    client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
    user_agent=os.getenv('REDDIT_USER_AGENT', 'BuyItForLifeSaleTracker/1.0'),
    username=os.getenv('REDDIT_USERNAME'),
    password=os.getenv('REDDIT_PASSWORD')
)


async def fetch_reddit_items() -> Dict[str, int]:
    """
    Fetch posts from the BuyItForLife subreddit and save them to the database.

    Returns:
        Dict with counts of new and updated items
    """
    try:
        # Use a background thread for Reddit API calls since they're blocking
        loop = asyncio.get_event_loop()
        top_posts = await loop.run_in_executor(
            None,
            lambda: list(reddit_client.subreddit('buyitforlife').top('month', limit=100))
        )

        new_items = 0
        updated_items = 0

        for post in top_posts:
            # Skip posts that are not product recommendations
            if hasattr(post, 'link_flair_text') and post.link_flair_text == 'Request':
                continue

            if post.is_self and not any(keyword in post.title.lower() for keyword in ['review', 'recommendation']):
                continue

            # Check if item already exists
            item = await Item.find_one(Item.reddit_id == post.id)

            if item:
                # Update existing item
                item.reddit_score = post.score
                item.reddit_comments = post.num_comments
                item.updated_at = datetime.now()
                await item.save()
                updated_items += 1
            else:
                # Create new item
                category = determine_category(post.title)

                # Extract image URL if available
                image_url = None
                if hasattr(post, 'preview') and 'images' in post.preview and len(post.preview['images']) > 0:
                    image_url = post.preview['images'][0]['source']['url']

                # Create new item
                item = Item(
                    title=cleanup_title(post.title),
                    description=post.selftext if hasattr(post, 'selftext') else '',
                    reddit_id=post.id,
                    reddit_url=f"https://reddit.com{post.permalink}",
                    reddit_score=post.score,
                    reddit_comments=post.num_comments,
                    reddit_posted_date=datetime.fromtimestamp(post.created_utc),
                    category=category,
                    image_url=image_url
                )

                await item.insert()
                new_items += 1

                # Extract product links and set up price tracking
                retailer_links = extract_retailer_links(
                    (post.selftext if hasattr(post, 'selftext') else '') + ' ' + post.url
                )

                if retailer_links:
                    for link in retailer_links:
                        await add_retailer_link(str(item.id), link)

        return {"new_items": new_items, "updated_items": updated_items}

    except RequestException as e:
        print(f"Reddit API error: {e}")
        return {"new_items": 0, "updated_items": 0}
    except Exception as e:
        print(f"Error fetching Reddit items: {e}")
        return {"new_items": 0, "updated_items": 0}


def cleanup_title(title: str) -> str:
    """Clean up item title by removing tags and formatting."""
    # Remove [Request] tag if present
    title = re.sub(r'\[request\]', '', title, flags=re.IGNORECASE)

    # Remove [Review] tag if present
    title = re.sub(r'\[review\]', '', title, flags=re.IGNORECASE)

    # Remove age information at the beginning like "[10 years]"
    title = re.sub(r'^\[\d+\s+(?:year|month|week|day)s?\]', '', title, flags=re.IGNORECASE)

    # Remove other common patterns in Reddit titles
    title = re.sub(r'^\[BIFL Request\]:', '', title, flags=re.IGNORECASE)
    title = re.sub(r'^\[BIFL\]:', '', title, flags=re.IGNORECASE)

    # Remove any remaining square brackets and their contents
    title = re.sub(r'\[.*?\]', '', title)

    # Remove multiple spaces and trim
    title = re.sub(r'\s+', ' ', title).strip()

    return title


def determine_category(title: str) -> str:
    """Determine the category based on title keywords."""
    title_lower = title.lower()

    categories = {
        'Kitchen': ['kitchen', 'cookware', 'knife', 'pan', 'pot', 'blender', 'mixer', 'food'],
        'Clothing': ['clothing', 'jacket', 'shirt', 'pant', 'jeans', 'coat', 'sweater', 'hoodie'],
        'Footwear': ['shoe', 'boot', 'footwear', 'sneaker', 'sandal'],
        'Bags': ['bag', 'backpack', 'luggage', 'suitcase', 'purse', 'wallet'],
        'Electronics': ['electronic', 'headphone', 'speaker', 'computer', 'laptop', 'phone', 'camera'],
        'Tools': ['tool', 'drill', 'hammer', 'screwdriver', 'wrench', 'knife', 'multitool'],
        'Furniture': ['furniture', 'chair', 'desk', 'table', 'sofa', 'couch', 'bed'],
        'Outdoors': ['outdoor', 'camping', 'hiking', 'tent', 'sleeping', 'backpack', 'thermos']
    }

    for category, keywords in categories.items():
        if any(keyword in title_lower for keyword in keywords):
            return category

    return 'Other'


def extract_retailer_links(content: str) -> List[Dict[str, Any]]:
    """Extract retailer links from post content."""
    retailer_domains = [
        {'name': 'Amazon', 'domain': 'amazon.com'},
        {'name': 'Amazon', 'domain': 'amzn.to'},
        {'name': 'eBay', 'domain': 'ebay.com'},
        {'name': 'Walmart', 'domain': 'walmart.com'},
        {'name': 'Target', 'domain': 'target.com'},
        {'name': 'Home Depot', 'domain': 'homedepot.com'},
        {'name': 'Best Buy', 'domain': 'bestbuy.com'},
        {'name': 'REI', 'domain': 'rei.com'},
        {'name': 'Etsy', 'domain': 'etsy.com'},
        {'name': 'Wayfair', 'domain': 'wayfair.com'}
    ]

    # Find URLs in the content
    url_regex = r'https?://[^\s)"]+'
    urls = re.findall(url_regex, content)

    links = []
    for url in urls:
        # Clean up URL (remove trailing punctuation that may have been caught)
        url = re.sub(r'[.,;:\"\']$', '', url)

        # Check if URL is from a known retailer
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        if 'www.' in domain:
            domain = domain.replace('www.', '')

        for retailer in retailer_domains:
            if retailer['domain'] in domain:
                retailer_name = retailer['name']

                # Create the link object with affiliate information
                link = {
                    'name': retailer_name,
                    'url': url,
                    'current_price': None,
                    'last_checked': None,
                    'affiliate_enabled': True,
                    'affiliate_url': None,
                    'affiliate_program': None
                }

                # Generate affiliate link
                affiliate_url = generate_affiliate_link(url, retailer_name)
                if affiliate_url:
                    link['affiliate_url'] = affiliate_url
                    link['affiliate_program'] = retailer_name.lower()

                links.append(link)
                break

    return links


async def add_retailer_link(item_id: str, retailer_link: Dict[str, Any]) -> None:
    """Add a retailer link to an item and check its price."""
    try:
        # Get the item
        item = await Item.get(item_id)
        if not item:
            return

        # Check if link already exists
        for link in item.retailer_links:
            if link.url == retailer_link['url']:
                return

        # Create new RetailerLink object
        new_link = RetailerLink(**retailer_link)

        # Add to item
        item.retailer_links.append(new_link)
        await item.save()

        # Schedule price check for this link
        await check_price_for_link(item_id, new_link)

    except Exception as e:
        print(f"Error adding retailer link: {e}")