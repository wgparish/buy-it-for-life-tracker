# app/utils/affiliate.py - Utility for generating affiliate links

import os
import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from typing import Optional, Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Affiliate program credentials
AMAZON_ASSOCIATE_ID = os.getenv('AMAZON_ASSOCIATE_ID', 'yourtag-20')
WALMART_AFFILIATE_ID = os.getenv('WALMART_AFFILIATE_ID', 'yourwalmartid')
TARGET_AFFILIATE_ID = os.getenv('TARGET_AFFILIATE_ID', 'yourtargetid')
BEST_BUY_AFFILIATE_ID = os.getenv('BEST_BUY_AFFILIATE_ID', 'yourbestbuyid')
EBAY_AFFILIATE_ID = os.getenv('EBAY_AFFILIATE_ID', 'yourebayid')

# Mapping of retailer to affiliate program processor function
AFFILIATE_PROCESSORS = {
    'Amazon': 'amazon',
    'Walmart': 'walmart',
    'Target': 'target',
    'Best Buy': 'best_buy',
    'eBay': 'ebay',
    'Home Depot': 'impact_radius',
    'REI': 'avantlink',
    'Etsy': 'awin',
    'Wayfair': 'cj'
}


def generate_affiliate_link(url: str, retailer: str) -> Optional[str]:
    """
    Generate an affiliate link for the given URL and retailer.

    Args:
        url: Original product URL
        retailer: Retailer name (Amazon, Walmart, etc.)

    Returns:
        str: Affiliate link, or None if no affiliate program is available
    """
    # Check if we have an affiliate program for this retailer
    program = AFFILIATE_PROCESSORS.get(retailer)
    if not program:
        return None

    # Call the appropriate affiliate link generator
    affiliate_func = globals().get(f"generate_{program}_link")
    if affiliate_func and callable(affiliate_func):
        return affiliate_func(url)

    return None


def generate_amazon_link(url: str) -> str:
    """Generate Amazon affiliate link."""
    # Parse the URL
    parsed_url = urlparse(url)

    # Extract ASIN if present in URL
    asin = None

    # Check if ASIN is in path (common pattern: /dp/ASIN or /gp/product/ASIN)
    if '/dp/' in parsed_url.path:
        asin = parsed_url.path.split('/dp/')[1].split('/')[0]
    elif '/gp/product/' in parsed_url.path:
        asin = parsed_url.path.split('/gp/product/')[1].split('/')[0]

    # If we have an ASIN, create a clean affiliate link
    if asin and len(asin) == 10:
        return f"https://www.amazon.com/dp/{asin}?tag={AMAZON_ASSOCIATE_ID}"

    # Otherwise, just add the affiliate tag to the original URL
    query_dict = parse_qs(parsed_url.query)
    query_dict['tag'] = [AMAZON_ASSOCIATE_ID]

    new_query = urlencode(query_dict, doseq=True)
    new_parts = list(parsed_url)
    new_parts[4] = new_query

    return urlunparse(new_parts)


def generate_walmart_link(url: str) -> str:
    """Generate Walmart affiliate link."""
    # Walmart typically uses Impact Radius / Walmart Affiliates
    parsed_url = urlparse(url)

    # Extract product ID if possible
    product_id = None
    if '/ip/' in parsed_url.path:
        path_parts = parsed_url.path.split('/')
        if len(path_parts) > 3:
            product_id = path_parts[3]

    # For Walmart, we'll use a simple query parameter approach
    query_dict = parse_qs(parsed_url.query)
    query_dict['wmlspartner'] = [WALMART_AFFILIATE_ID]

    new_query = urlencode(query_dict, doseq=True)
    new_parts = list(parsed_url)
    new_parts[4] = new_query

    return urlunparse(new_parts)


def generate_target_link(url: str) -> str:
    """Generate Target affiliate link."""
    # Target typically uses Impact Radius
    # Simplified implementation - in production, you might use their API
    parsed_url = urlparse(url)

    query_dict = parse_qs(parsed_url.query)
    query_dict['afid'] = [TARGET_AFFILIATE_ID]

    new_query = urlencode(query_dict, doseq=True)
    new_parts = list(parsed_url)
    new_parts[4] = new_query

    return urlunparse(new_parts)


def generate_best_buy_link(url: str) -> str:
    """Generate Best Buy affiliate link."""
    # Best Buy typically uses Impact Radius or their own system
    parsed_url = urlparse(url)

    query_dict = parse_qs(parsed_url.query)
    query_dict['irclickid'] = [BEST_BUY_AFFILIATE_ID]

    new_query = urlencode(query_dict, doseq=True)
    new_parts = list(parsed_url)
    new_parts[4] = new_query

    return urlunparse(new_parts)


def generate_ebay_link(url: str) -> str:
    """Generate eBay affiliate link."""
    # eBay typically uses their partner network
    parsed_url = urlparse(url)

    query_dict = parse_qs(parsed_url.query)
    query_dict['mkrid'] = [EBAY_AFFILIATE_ID]

    new_query = urlencode(query_dict, doseq=True)
    new_parts = list(parsed_url)
    new_parts[4] = new_query

    return urlunparse(new_parts)


def generate_impact_radius_link(url: str) -> str:
    """Generic Impact Radius affiliate link generator."""
    # Simplified implementation
    return url + (('&' if '?' in url else '?') + 'ir-affiliate=true')


def generate_avantlink_link(url: str) -> str:
    """Generate AvantLink affiliate link."""
    # Simplified implementation
    return url + (('&' if '?' in url else '?') + 'avantlink=true')


def generate_awin_link(url: str) -> str:
    """Generate AWIN affiliate link."""
    # Simplified implementation
    return url + (('&' if '?' in url else '?') + 'awin=true')


def generate_cj_link(url: str) -> str:
    """Generate Commission Junction affiliate link."""
    # Simplified implementation
    return url + (('&' if '?' in url else '?') + 'cj=true')