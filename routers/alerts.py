# app/routers/alerts.py - Updated Alerts router with Auth0 integration

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime
from fastapi_auth0 import Auth0User


from auth_config import require_scope, get_user_id, require_user
from database import User, Item, Alert, get_or_create_user
from models import AlertCreate, AlertUpdate, AlertResponse
from routers.items import item_to_response

router = APIRouter()


# Helper function to convert alert to response model
def alert_to_response(alert: Alert, include_item: bool = False) -> AlertResponse:
    response = AlertResponse(
        id=str(alert.id),
        user_id=alert.user_id,
        item_id=alert.item_id,
        price_threshold=alert.price_threshold,
        price_drop_percentage=alert.price_drop_percentage,
        is_active=alert.is_active,
        last_triggered=alert.last_triggered,
        created_at=alert.created_at
    )

    return response


# Routes
@router.post("/subscribe", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def subscribe_to_item(
        alert_data: AlertCreate,
        user: Auth0User = Depends(require_scope("write:alerts"))
):
    auth0_user_id = get_user_id(user)
    email = user.get("email", "")

    # Get or create user in our database
    db_user = await get_or_create_user(auth0_user_id, email)

    # Check if item exists
    item = await Item.get(alert_data.item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )

    # Check if user is already subscribed
    existing_alert = await Alert.find_one(
        Alert.user_id == auth0_user_id,
        Alert.item_id == alert_data.item_id
    )

    if existing_alert:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already subscribed to this item"
        )

    # Create new alert
    new_alert = Alert(
        user_id=auth0_user_id,
        item_id=alert_data.item_id,
        price_threshold=alert_data.price_threshold,
        price_drop_percentage=alert_data.price_drop_percentage
    )

    await new_alert.insert()

    # Add user to item's subscribers if not already there
    if auth0_user_id not in item.subscribers:
        item.subscribers.append(auth0_user_id)
        await item.save()

    # Add item to user's items if not already there
    if alert_data.item_id not in db_user.items:
        db_user.items.append(alert_data.item_id)
        await db_user.save()

    return alert_to_response(new_alert)


@router.delete("/unsubscribe/{item_id}", status_code=status.HTTP_200_OK)
async def unsubscribe_from_item(
        item_id: str,
        user: Auth0User = Depends(require_scope("write:alerts"))
):
    auth0_user_id = get_user_id(user)

    # Get user from database
    db_user = await User.find_one(User.auth0_id == auth0_user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Delete alert
    alert = await Alert.find_one(
        Alert.user_id == auth0_user_id,
        Alert.item_id == item_id
    )

    if alert:
        await alert.delete()

    # Remove user from item's subscribers
    item = await Item.get(item_id)
    if item and auth0_user_id in item.subscribers:
        item.subscribers.remove(auth0_user_id)
        await item.save()

    # Remove item from user's items
    if item_id in db_user.items:
        db_user.items.remove(item_id)
        await db_user.save()

    return {"message": "Unsubscribed successfully"}


@router.get("/my-alerts", response_model=List[AlertResponse])
async def get_user_alerts(
        user: Auth0User = Depends(require_scope("read:alerts")),
        include_items: bool = False
):
    auth0_user_id = get_user_id(user)

    # Find all alerts for current user
    alerts = await Alert.find(Alert.user_id == auth0_user_id).to_list()

    # Convert to response models
    alert_responses = []
    for alert in alerts:
        response = alert_to_response(alert)

        # Include item data if requested
        if include_items:
            item = await Item.get(alert.item_id)
            if item:
                response.item = item_to_response(item)

        alert_responses.append(response)

    return alert_responses


@router.put("/update/{alert_id}", response_model=AlertResponse)
async def update_alert(
        alert_id: str,
        alert_data: AlertUpdate,
        user: Auth0User = Depends(require_scope("write:alerts"))
):
    auth0_user_id = get_user_id(user)

    # Find alert
    alert = await Alert.find_one(
        Alert.id == alert_id,
        Alert.user_id == auth0_user_id
    )

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    # Update fields
    if alert_data.price_threshold is not None:
        alert.price_threshold = alert_data.price_threshold

    if alert_data.price_drop_percentage is not None:
        alert.price_drop_percentage = alert_data.price_drop_percentage

    if alert_data.is_active is not None:
        alert.is_active = alert_data.is_active

    # Save changes
    await alert.save()

    return alert_to_response(alert)


@router.get("/check-subscription/{item_id}")
async def check_subscription(
        item_id: str,
        user: Auth0User = Depends(require_user)
):
    auth0_user_id = get_user_id(user)

    # Check if alert exists
    alert = await Alert.find_one(
        Alert.user_id == auth0_user_id,
        Alert.item_id == item_id
    )

    return {
        "subscribed": alert is not None,
        "alert_id": str(alert.id) if alert else None,
        "is_active": alert.is_active if alert else False
    }