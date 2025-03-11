# app/routers/items.py - Updated Items router with Auth0 integration

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
import re
from fastapi_auth0 import Auth0User

from database import User, Item
from models import ItemResponse, ItemsResponse, RedditFetchResponse
from utils.reddit import fetch_reddit_items
from auth_config import require_scope, get_user_id

router = APIRouter()


# Helper to convert DB Item to response model
def item_to_response(item: Item) -> ItemResponse:
    return ItemResponse(
        id=str(item.id),
        title=item.title,
        description=item.description,
        reddit_id=item.reddit_id,
        reddit_url=item.reddit_url,
        reddit_score=item.reddit_score,
        reddit_comments=item.reddit_comments,
        reddit_posted_date=item.reddit_posted_date,
        category=item.category,
        image_url=item.image_url,
        current_price=item.current_price,
        currency=item.currency,
        price_history=item.price_history,
        retailer_links=item.retailer_links,
        subscribers_count=len(item.subscribers),
        is_on_sale=item.is_on_sale,
        created_at=item.created_at,
        updated_at=item.updated_at
    )


# Routes
@router.get("", response_model=ItemsResponse)
async def get_items(
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=100),
        search: Optional[str] = None,
        category: Optional[str] = None,
        sort_by: str = "reddit_score",
        sort_order: str = "desc",
        user: Auth0User = Depends(require_scope("read:items"))
):
    # Calculate skip
    skip = (page - 1) * limit

    # Build filter
    filter_dict = {}
    if search:
        # Basic text search (in a production app, use proper text search indexes)
        search_regex = re.compile(f".*{re.escape(search)}.*", re.IGNORECASE)
        filter_dict["$or"] = [
            {"title": {"$regex": search_regex}},
            {"description": {"$regex": search_regex}}
        ]

    if category:
        filter_dict["category"] = category

    # Validate sort field
    valid_sort_fields = ["reddit_score", "created_at", "updated_at", "current_price", "title"]
    if sort_by not in valid_sort_fields:
        sort_by = "reddit_score"

    # Determine sort direction
    sort_direction = -1 if sort_order.lower() == "desc" else 1

    # Query database
    items_cursor = Item.find(filter_dict)

    # Apply sorting
    items_cursor = items_cursor.sort([(sort_by, sort_direction)])

    # Apply pagination
    items_cursor = items_cursor.skip(skip).limit(limit)

    # Get items and total count
    items = await items_cursor.to_list()
    total = await Item.find(filter_dict).count()

    # Convert to response models
    item_responses = [item_to_response(item) for item in items]

    return ItemsResponse(
        items=item_responses,
        total_pages=(total + limit - 1) // limit,  # Ceiling division
        current_page=page,
        total_items=total
    )


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(
        item_id: str,
        user: Auth0User = Depends(require_scope("read:items"))
):
    item = await Item.get(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )

    return item_to_response(item)


@router.post("/refresh-reddit", response_model=RedditFetchResponse)
async def refresh_reddit_items(
        user: Auth0User = Depends(require_scope("write:items"))
):
    # In a production app, add admin role check here
    # This could be done by checking a specific permission in the Auth0 token
    # For example:
    # permissions = user.get("permissions", [])
    # if "admin:items" not in permissions:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Admin access required"
    #     )

    result = await fetch_reddit_items()

    return RedditFetchResponse(
        message="Reddit items refreshed",
        new_items=result["new_items"],
        updated_items=result["updated_items"]
    )


@router.get("/categories/all", response_model=List[str])
async def get_categories(
        user: Auth0User = Depends(require_scope("read:items"))
):
    # Get distinct categories
    # Note: Motor doesn't have direct distinct method, so we fetch all and process
    items = await Item.find().to_list()
    categories = set()

    for item in items:
        if item.category:
            categories.add(item.category)

    return sorted(list(categories))


@router.get("/user-items", response_model=List[ItemResponse])
async def get_user_items(
        user: Auth0User = Depends(require_scope("read:items"))
):
    auth0_user_id = get_user_id(user)

    # Find the user in our database
    db_user = await User.find_one(User.auth0_id == auth0_user_id)

    if not db_user or not db_user.items:
        return []

    # Find all items that the user is subscribed to
    items = []
    for item_id in db_user.items:
        item = await Item.get(item_id)
        if item:
            items.append(item)

    # Convert to response models
    return [item_to_response(item) for item in items]


@router.get("/on-sale", response_model=List[ItemResponse])
async def get_items_on_sale(
        user: Auth0User = Depends(require_scope("read:items"))
):
    # Find all items that are on sale
    items = await Item.find(Item.is_on_sale == True).to_list()

    # Convert to response models
    return [item_to_response(item) for item in items]