# app/routers/affiliate.py - Routes for affiliate link handling and tracking

from fastapi import APIRouter, Depends, HTTPException, Request, status, Response
from fastapi.responses import RedirectResponse
from fastapi_auth0 import Auth0User
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from database.database import Item, User, get_or_create_user
from auth.auth_config import auth, require_user, require_scope, get_user_id
from utils.tracking import track_affiliate_click, get_affiliate_stats
from utils.affiliate import generate_affiliate_link

router = APIRouter()


@router.get("/redirect/{item_id}")
async def affiliate_redirect(
        item_id: str,
        request: Request,
        retailer: Optional[str] = None,
        user: Optional[Auth0User] = Depends(auth.get_user)
):
    """
    Redirect to an affiliate link for the given item, tracking the click.

    Args:
        item_id: ID of the item
        retailer: Optional retailer name to specify which retailer link to use
        user: Optional user info from Auth0

    Returns:
        RedirectResponse to the affiliate link
    """
    # Get the item
    item = await Item.get(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )

    # Find the appropriate retailer link
    chosen_link = None
    if retailer:
        # Find the specific retailer link if requested
        for link in item.retailer_links:
            if link.name.lower() == retailer.lower():
                chosen_link = link
                break
    else:
        # Otherwise use the first link with the lowest price
        valid_links = [link for link in item.retailer_links if link.current_price is not None]
        if valid_links:
            chosen_link = min(valid_links, key=lambda x: x.current_price)
        else:
            # If no links with prices, use the first link
            chosen_link = item.retailer_links[0] if item.retailer_links else None

    if not chosen_link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No retailer link found for this item"
        )

    # Get user ID if available
    user_id = get_user_id(user) if user else None

    # Get or generate affiliate link
    affiliate_url = chosen_link.affiliate_url
    if not affiliate_url and chosen_link.affiliate_enabled:
        affiliate_url = generate_affiliate_link(chosen_link.url, chosen_link.name)
        if affiliate_url:
            # Update the item with the new affiliate link
            for i, link in enumerate(item.retailer_links):
                if link.url == chosen_link.url:
                    item.retailer_links[i].affiliate_url = affiliate_url
                    item.retailer_links[i].affiliate_program = chosen_link.name.lower()
                    await item.save()
                    break

    # If no affiliate link available, use the regular link
    final_url = affiliate_url if affiliate_url else chosen_link.url

    # Track the click
    affiliate_program = chosen_link.affiliate_program or chosen_link.name.lower()
    await track_affiliate_click(
        request=request,
        item_id=item_id,
        retailer=chosen_link.name,
        affiliate_program=affiliate_program,
        user_id=user_id
    )

    # Redirect to the final URL
    response = RedirectResponse(url=final_url)

    # Set a cookie for potential conversion tracking
    response.set_cookie(
        key="bifl_click",
        value=f"{item_id}:{chosen_link.name}",
        max_age=30 * 24 * 60 * 60,  # 30 days
        httponly=True,
        samesite="lax"
    )

    return response


@router.get("/stats", response_model=Dict[str, Any])
async def get_affiliate_statistics(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        affiliate_program: Optional[str] = None,
        user: Auth0User = Depends(require_scope("read:admin"))
):
    """
    Get statistics about affiliate link clicks and conversions.

    Args:
        start_date: Optional start date in format YYYY-MM-DD
        end_date: Optional end date in format YYYY-MM-DD
        affiliate_program: Optional affiliate program for filtering
        user: Auth0 user with admin permissions

    Returns:
        Dict with statistics about clicks and conversions
    """
    # Parse dates if provided
    start_datetime = None
    if start_date:
        try:
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use YYYY-MM-DD."
            )

    end_datetime = None
    if end_date:
        try:
            # Set end_datetime to the end of the day
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
            end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format. Use YYYY-MM-DD."
            )

    # If no dates provided, default to last 30 days
    if not start_datetime and not end_datetime:
        end_datetime = datetime.now()
        start_datetime = end_datetime - timedelta(days=30)

    # Get statistics
    stats = await get_affiliate_stats(
        start_date=start_datetime,
        end_date=end_datetime,
        affiliate_program=affiliate_program
    )

    return stats


@router.get("/popular", response_model=Dict[str, Any])
async def get_popular_affiliate_items(
        days: int = 30,
        limit: int = 10,
        user: Auth0User = Depends(require_scope("read:admin"))
):
    """
    Get the most popular items based on affiliate link clicks.

    Args:
        days: Number of days to look back
        limit: Maximum number of items to return
        user: Auth0 user with admin permissions

    Returns:
        Dict with popular items and their click statistics
    """
    from app.utils.tracking import click_collection
    from bson.objectid import ObjectId
    import motor.motor_asyncio

    # Calculate start date
    start_date = datetime.now() - timedelta(days=days)

    # Aggregate clicks by item
    pipeline = [
        {"$match": {"timestamp": {"$gte": start_date}}},
        {"$group": {
            "_id": "$item_id",
            "clicks": {"$sum": 1},
            "conversions": {"$sum": {"$cond": [{"$eq": ["$converted", True]}, 1, 0]}},
            "revenue": {"$sum": {"$ifNull": ["$revenue", 0]}}
        }},
        {"$sort": {"clicks": -1}},
        {"$limit": limit}
    ]

    result = await click_collection.aggregate(pipeline).to_list(length=None)

    # Get item details for each popular item
    popular_items = []
    for item_stats in result:
        item_id = item_stats["_id"]
        try:
            item = await Item.get(item_id)
            if item:
                conversion_rate = (item_stats["conversions"] / item_stats["clicks"]) * 100 if item_stats[
                                                                                                  "clicks"] > 0 else 0

                popular_items.append({
                    "item": {
                        "id": str(item.id),
                        "title": item.title,
                        "category": item.category,
                        "current_price": item.current_price,
                        "image_url": item.image_url
                    },
                    "stats": {
                        "clicks": item_stats["clicks"],
                        "conversions": item_stats["conversions"],
                        "conversion_rate": conversion_rate,
                        "revenue": item_stats["revenue"]
                    }
                })
        except Exception as e:
            print(f"Error getting item {item_id}: {e}")

    return {
        "popular_items": popular_items,
        "period": {
            "days": days,
            "start_date": start_date,
            "end_date": datetime.now()
        }
    }