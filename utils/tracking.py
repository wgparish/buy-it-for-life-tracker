# app/utils/tracking.py - Utilities for tracking affiliate link clicks

import os
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel
from fastapi import Request
from dotenv import load_dotenv

from database.database import User, Item, db

# Load environment variables
load_dotenv()

# Collection for tracking clicks
click_collection = db.affiliate_clicks


class ClickData(BaseModel):
    user_id: Optional[str] = None
    item_id: str
    retailer: str
    affiliate_program: str
    timestamp: datetime = datetime.now()
    referrer: Optional[str] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None  # Store hashed or anonymized in production
    converted: bool = False
    revenue: Optional[float] = None


async def track_affiliate_click(
        request: Request,
        item_id: str,
        retailer: str,
        affiliate_program: str,
        user_id: Optional[str] = None
) -> str:
    """
    Track an affiliate link click and return the affiliate URL.

    Args:
        request: FastAPI request object
        item_id: ID of the item being clicked
        retailer: Name of the retailer
        affiliate_program: Name of the affiliate program
        user_id: Optional user ID if user is logged in

    Returns:
        str: Tracking ID for this click
    """
    # Get request information
    user_agent = request.headers.get("user-agent", "")
    referrer = request.headers.get("referer", "")
    ip = request.client.host if request.client else None

    # Create click tracking data
    click_data = {
        "user_id": user_id,
        "item_id": item_id,
        "retailer": retailer,
        "affiliate_program": affiliate_program,
        "timestamp": datetime.now(),
        "referrer": referrer,
        "user_agent": user_agent,
        "ip_address": ip,  # In production, hash or anonymize this
        "converted": False,
        "revenue": None
    }

    # Insert into database
    result = await click_collection.insert_one(click_data)

    # Return the ID of the click record
    return str(result.inserted_id)


async def update_conversion(
        tracking_id: str,
        converted: bool = True,
        revenue: Optional[float] = None
) -> bool:
    """
    Update a click record with conversion information.

    Args:
        tracking_id: The tracking ID returned by track_affiliate_click
        converted: Whether the click resulted in a conversion
        revenue: Optional revenue amount from the conversion

    Returns:
        bool: True if the update was successful, False otherwise
    """
    try:
        from bson.objectid import ObjectId

        # Update the click record
        result = await click_collection.update_one(
            {"_id": ObjectId(tracking_id)},
            {"$set": {
                "converted": converted,
                "revenue": revenue,
                "conversion_timestamp": datetime.now()
            }}
        )

        return result.modified_count > 0
    except Exception as e:
        print(f"Error updating conversion: {e}")
        return False


async def get_affiliate_stats(
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        affiliate_program: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get statistics about affiliate link clicks and conversions.

    Args:
        start_date: Optional start date for filtering
        end_date: Optional end date for filtering
        affiliate_program: Optional affiliate program for filtering

    Returns:
        Dict with statistics about clicks and conversions
    """
    # Build query
    query = {}
    if start_date or end_date:
        query["timestamp"] = {}
        if start_date:
            query["timestamp"]["$gte"] = start_date
        if end_date:
            query["timestamp"]["$lte"] = end_date

    if affiliate_program:
        query["affiliate_program"] = affiliate_program

    # Get all matching clicks
    clicks = await click_collection.find(query).to_list(length=None)

    # Calculate statistics
    total_clicks = len(clicks)
    conversions = [click for click in clicks if click.get("converted", False)]
    total_conversions = len(conversions)
    total_revenue = sum(click.get("revenue", 0) for click in conversions if click.get("revenue"))

    # Calculate conversion rate
    conversion_rate = (total_conversions / total_clicks) * 100 if total_clicks > 0 else 0

    # Get statistics by retailer
    retailers = {}
    for click in clicks:
        retailer = click.get("retailer", "Unknown")
        if retailer not in retailers:
            retailers[retailer] = {
                "clicks": 0,
                "conversions": 0,
                "revenue": 0
            }

        retailers[retailer]["clicks"] += 1
        if click.get("converted", False):
            retailers[retailer]["conversions"] += 1
            retailers[retailer]["revenue"] += click.get("revenue", 0) or 0

    # Calculate conversion rates for each retailer
    for retailer in retailers:
        retailers[retailer]["conversion_rate"] = (
            (retailers[retailer]["conversions"] / retailers[retailer]["clicks"]) * 100
            if retailers[retailer]["clicks"] > 0 else 0
        )

    return {
        "total_clicks": total_clicks,
        "total_conversions": total_conversions,
        "conversion_rate": conversion_rate,
        "total_revenue": total_revenue,
        "retailers": retailers,
        "period": {
            "start_date": start_date,
            "end_date": end_date
        }
    }