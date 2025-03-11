# app/database.py - Updated database models for Auth0 integration

import os
import motor.motor_asyncio
from beanie import Document, Indexed, Link, init_beanie
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime
import uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB connection
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "buyitforlife")

# Connect to MongoDB
client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
db = client[DATABASE_NAME]


# Base models for shared fields
class TimestampModel(BaseModel):
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class PriceHistory(BaseModel):
    price: float
    date: datetime = Field(default_factory=datetime.now)


class RetailerLink(BaseModel):
    name: str
    url: str
    current_price: Optional[float] = None
    price_dropped: bool = False
    last_checked: Optional[datetime] = None


class UserNotified(BaseModel):
    user_id: str
    sent_at: datetime = Field(default_factory=datetime.now)


# MongoDB Document Models - Updated for Auth0
class User(Document, TimestampModel):
    auth0_id: Indexed(str, unique=True)  # Auth0 user ID (sub)
    email: str  # Auth0 will verify emails
    items: List[str] = []  # List of item IDs user is tracking
    preferences: dict = {}  # User preferences
    last_login: Optional[datetime] = None

    class Settings:
        name = "users"
        use_revision = True


class Item(Document, TimestampModel):
    title: str
    description: Optional[str] = None
    reddit_id: Indexed(str, unique=True)
    reddit_url: str
    reddit_score: Optional[int] = None
    reddit_comments: Optional[int] = None
    reddit_posted_date: Optional[datetime] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    current_price: Optional[float] = None
    currency: str = "USD"
    price_history: List[PriceHistory] = []
    retailer_links: List[RetailerLink] = []
    subscribers: List[str] = []  # List of Auth0 user IDs
    is_on_sale: bool = False

    class Settings:
        name = "items"
        use_revision = True


class Alert(Document, TimestampModel):
    user_id: str  # Auth0 user ID
    item_id: str
    price_threshold: Optional[float] = None
    price_drop_percentage: Optional[float] = None
    is_active: bool = True
    last_triggered: Optional[datetime] = None
    notification_channels: List[str] = ["email"]  # Can include "sms", "push", etc.

    class Settings:
        name = "alerts"


class PriceUpdate(Document, TimestampModel):
    item_id: str
    retailer: str
    old_price: float
    new_price: float
    percentage_change: float
    notifications_sent: bool = False
    users_notified: List[UserNotified] = []

    class Settings:
        name = "price_updates"


# Initialize database
async def init_db():
    """Initialize the database with Beanie ODM"""
    await init_beanie(
        database=db,
        document_models=[
            User,
            Item,
            Alert,
            PriceUpdate
        ]
    )


# Helper functions
async def get_or_create_user(auth0_id: str, email: str):
    """Get an existing user or create a new one based on Auth0 ID"""
    user = await User.find_one(User.auth0_id == auth0_id)

    if not user:
        user = User(
            auth0_id=auth0_id,
            email=email,
            last_login=datetime.now()
        )
        await user.insert()
    else:
        # Update last login
        user.last_login = datetime.now()
        await user.save()

    return user