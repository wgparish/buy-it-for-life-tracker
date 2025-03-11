# app/models.py - Pydantic models for request/response schemas

from pydantic import BaseModel, EmailStr, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
import re


# User models
class UserCreate(BaseModel):
    email: EmailStr
    password: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @validator('password')
    def password_must_be_strong(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        return v


class UserResponse(BaseModel):
    id: str
    email: str
    email_verified: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class EmailRequest(BaseModel):
    email: EmailStr


class PasswordReset(BaseModel):
    password: str

    @validator('password')
    def password_must_be_strong(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        return v


# Item models
class RetailerLinkModel(BaseModel):
    name: str
    url: str
    current_price: Optional[float] = None
    price_dropped: bool = False
    last_checked: Optional[datetime] = None


class PriceHistoryModel(BaseModel):
    price: float
    date: datetime


class ItemResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    reddit_id: str
    reddit_url: str
    reddit_score: Optional[int] = None
    reddit_comments: Optional[int] = None
    reddit_posted_date: Optional[datetime] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    current_price: Optional[float] = None
    currency: str = "USD"
    price_history: List[PriceHistoryModel] = []
    retailer_links: List[RetailerLinkModel] = []
    subscribers_count: int = 0
    is_on_sale: bool = False
    created_at: datetime
    updated_at: datetime


class ItemsResponse(BaseModel):
    items: List[ItemResponse]
    total_pages: int
    current_page: int
    total_items: int


# Alert models
class AlertCreate(BaseModel):
    item_id: str
    price_threshold: Optional[float] = None
    price_drop_percentage: Optional[float] = None


class AlertUpdate(BaseModel):
    price_threshold: Optional[float] = None
    price_drop_percentage: Optional[float] = None
    is_active: Optional[bool] = None


class AlertResponse(BaseModel):
    id: str
    user_id: str
    item_id: str
    item: Optional[ItemResponse] = None
    price_threshold: Optional[float] = None
    price_drop_percentage: Optional[float] = None
    is_active: bool
    last_triggered: Optional[datetime] = None
    created_at: datetime


# Price update models
class UserNotifiedModel(BaseModel):
    user_id: str
    sent_at: datetime


class PriceUpdateResponse(BaseModel):
    id: str
    item_id: str
    retailer: str
    old_price: float
    new_price: float
    percentage_change: float
    notifications_sent: bool
    users_notified: List[UserNotifiedModel] = []
    created_at: datetime


# Reddit fetch response
class RedditFetchResponse(BaseModel):
    new_items: int
    updated_items: int
    message: str = "Reddit items refreshed"