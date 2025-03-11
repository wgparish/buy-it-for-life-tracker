# app/utils/price_tracker.py - Price tracking and notification functions

import asyncio
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import aiohttp
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from database import Item, PriceUpdate, Alert, User, PriceHistory, RetailerLink
from utils.email import send_price_alert_email

# Load environment variables
load_dotenv()


async def check_prices_and_notify() -> Dict[str, int]:
    """
    Check prices for all tracked items and send notifications if prices have dropped.

    Returns:
        Dict with counts of checked items and found price drops
    """
    try:
        # Get all items with retailer links
        items = await Item.find(
            {"retailer_links.0": {"$exists": True}}
        ).to_list()

        items_checked = 0
        price_drops_found = 0

        for item in items:
            for i, link in enumerate(item.retailer_links):
                price_dropped = await check_price_for_link(str(item.id), link)
                if price_dropped:
                    price_drops_found += 1

            items_checked += 1

        return {
            "items_checked": items_checked,
            "price_drops_found": price_drops_found
        }

    except Exception as e:
        print(f"Error checking prices: {e}")
        return {"items_checked": 0, "price_drops_found": 0}


async def check_price_for_link(item_id: str, retailer_link: RetailerLink) -> bool:
    """
    Check the price for a specific retailer link and update the item.
    Returns True if price has dropped.
    """
    try:
        item = await Item.get(item_id)
        if not item:
            return False

        # Extract price from the retailer's webpage
        price = await extract_price(retailer_link.url, retailer_link.name)

        # If price couldn't be extracted, return
        if price is None:
            return False

        # Update the item with the new price info
        index = -1
        for i, link in enumerate(item.retailer_links):
            if link.url == retailer_link.url:
                index = i
                break

        if index == -1:
            return False

        old_price = item.retailer_links[index].current_price
        price_dropped = False

        # If this is the first time checking or price has changed
        if old_price is None or price != old_price:
            # Update retailer link
            item.retailer_links[index].current_price = price
            item.retailer_links[index].last_checked = datetime.now()

            # Add to price history if price is new or has changed
            if old_price is None or price < old_price:
                # Add to price history
                item.price_history.append(PriceHistory(
                    price=price,
                    date=datetime.now()
                ))

                # If price has dropped
                if old_price is not None and price < old_price:
                    price_dropped = True
                    item.retailer_links[index].price_dropped = True

                    # Set item on sale flag
                    item.is_on_sale = True

                    # Calculate percentage change
                    percentage_change = ((old_price - price) / old_price) * 100

                    # Record the price update
                    price_update = PriceUpdate(
                        item_id=item_id,
                        retailer=item.retailer_links[index].name,
                        old_price=old_price,
                        new_price=price,
                        percentage_change=percentage_change
                    )
                    await price_update.insert()

                    # Send notifications to subscribers
                    await notify_subscribers(item, price_update)

            # Update item's current price with the lowest price available
            current_prices = [link.current_price for link in item.retailer_links
                              if link.current_price is not None]
            if current_prices:
                item.current_price = min(current_prices)

            # Save the item
            await item.save()

        return price_dropped

    except Exception as e:
        print(f"Error checking price for {retailer_link.url}: {e}")
        return False


async def extract_price(url: str, retailer: str) -> Optional[float]:
    """Extract price from retailer website."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Connection': 'keep-alive',
        'DNT': '1',  # Do Not Track
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as response:
                if response.status != 200:
                    return None

                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')

                # Different extraction strategies based on retailer
                if retailer == 'Amazon':
                    return extract_amazon_price(soup)
                elif retailer == 'Walmart':
                    return extract_walmart_price(soup)
                elif retailer == 'Target':
                    return extract_target_price(soup)
                elif retailer == 'Best Buy':
                    return extract_bestbuy_price(soup)
                else:
                    # Generic price extraction
                    return extract_generic_price(soup)

    except Exception as e:
        print(f"Error fetching price from {url}: {e}")
        return None


def extract_amazon_price(soup: BeautifulSoup) -> Optional[float]:
    """Extract price from Amazon product page."""
    # Try different price selectors
    price_selectors = [
        'span.a-offscreen',
        '#priceblock_ourprice',
        '#priceblock_dealprice',
        '#priceblock_saleprice',
        '.a-price .a-offscreen'
    ]

    for selector in price_selectors:
        price_elem = soup.select_one(selector)
        if price_elem:
            price_text = price_elem.text.strip()
            return parse_price(price_text)

    return None


def extract_walmart_price(soup: BeautifulSoup) -> Optional[float]:
    """Extract price from Walmart product page."""
    # Try different price selectors
    price_elem = soup.select_one('[itemprop="price"]')
    if price_elem:
        return parse_price(price_elem.get('content'))

    price_elem = soup.select_one('.price-characteristic')
    if price_elem:
        dollars = price_elem.get('content', '0')
        cents_elem = soup.select_one('.price-mantissa')
        cents = cents_elem.text.strip() if cents_elem else '00'
        return parse_price(f"{dollars}.{cents}")

    return None


def extract_target_price(soup: BeautifulSoup) -> Optional[float]:
    """Extract price from Target product page."""
    price_elem = soup.select_one('[data-test="product-price"]')
    if price_elem:
        return parse_price(price_elem.text)

    return None


def extract_bestbuy_price(soup: BeautifulSoup) -> Optional[float]:
    """Extract price from Best Buy product page."""
    price_elem = soup.select_one('.priceView-customer-price > span')
    if price_elem:
        return parse_price(price_elem.text)

    return None


def extract_generic_price(soup: BeautifulSoup) -> Optional[float]:
    """Generic price extraction strategy."""
    # Try common price patterns across different sites
    price_patterns = [
        r'\$\s*(\d+(?:,\d+)*\.?\d*)',  # $XX.XX or $XX
        r'(\d+(?:,\d+)*\.?\d*)\s*USD',  # XX.XX USD or XX USD
        r'Price:\s*\$\s*(\d+(?:,\d+)*\.?\d*)',  # Price: $XX.XX
        r'(\d+(?:,\d+)*\.?\d*)'  # Just numbers as a fallback
    ]

    # Look for elements likely to contain price information
    price_containers = soup.select(
        '[class*="price"], [id*="price"], [class*="Price"], [id*="Price"]'
    )

    # Try to find price in these containers
    for container in price_containers:
        text = container.text.strip()
        for pattern in price_patterns:
            match = re.search(pattern, text)
            if match:
                return parse_price(match.group(1))

    # If no price found in containers, try the whole page
    text = soup.text
    for pattern in price_patterns:
        match = re.search(pattern, text)
        if match:
            return parse_price(match.group(1))

    return None


def parse_price(price_text: str) -> Optional[float]:
    """Parse price text into a float."""
    if not price_text:
        return None

    # Remove currency symbols and non-numeric characters except decimal point
    price_text = re.sub(r'[^\d.]', '', price_text.replace(',', ''))

    try:
        return float(price_text)
    except ValueError:
        return None


async def notify_subscribers(item: Item, price_update: PriceUpdate) -> None:
    """Send notifications to subscribers when a price drops."""
    if not item.subscribers:
        return

    # Mark the price update as having notifications sent
    price_update.notifications_sent = True

    # Get all alerts for this item
    alerts = await Alert.find(
        Alert.item_id == str(item.id),
        Alert.is_active == True
    ).to_list()

    # Group alerts by user for efficient processing
    user_alerts = {}
    for alert in alerts:
        if alert.user_id not in user_alerts:
            user_alerts[alert.user_id] = []
        user_alerts[alert.user_id].append(alert)

    # Process each user
    for user_id, user_alerts_list in user_alerts.items():
        user = await User.find_one(User.auth0_id == user_id)
        if not user or not user.email:
            continue

        # Check if any alert criteria are met
        should_notify = False
        for alert in user_alerts_list:
            # Price threshold check
            if alert.price_threshold is not None and price_update.new_price <= alert.price_threshold:
                should_notify = True
                alert.last_triggered = datetime.now()
                await alert.save()

            # Price drop percentage check
            if alert.price_drop_percentage is not None and price_update.percentage_change >= alert.price_drop_percentage:
                should_notify = True
                alert.last_triggered = datetime.now()
                await alert.save()

            # Default notification (no specific criteria)
            if alert.price_threshold is None and alert.price_drop_percentage is None:
                should_notify = True
                alert.last_triggered = datetime.now()
                await alert.save()

        # Send notification if any criteria are met
        if should_notify:
            await send_price_alert_email(
                user.email,
                item,
                price_update.old_price,
                price_update.new_price,
                price_update.percentage_change
            )

            # Record that this user was notified
            price_update.users_notified.append({
                "user_id": user_id,
                "sent_at": datetime.now()
            })

    # Save the updated price update
    await price_update.save()