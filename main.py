# main.py - Main FastAPI application with Auth0 integration
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
import uvicorn
import os
from datetime import datetime
from dotenv import load_dotenv

# Import local modules
from database import init_db
from routers import items, alerts
from utils.reddit import fetch_reddit_items
from utils.price_tracker import check_prices_and_notify
from auth_config import auth

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="BuyItForLife Sale Tracker API",
    description="API for tracking Reddit's BuyItForLife items and their prices",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "*")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers - No more need for the auth router since Auth0 handles that
app.include_router(items.router, prefix="/api/items", tags=["Items"])
app.include_router(alerts.router, prefix="/api/alerts", tags=["Alerts"])


# Initialize database at startup
@app.on_event("startup")
async def startup_db_client():
    await init_db()
    init_scheduler()


# Close database connection on shutdown
@app.on_event("shutdown")
async def shutdown_db_client():
    # MongoDB connections are closed automatically by Motor
    pass


# Initialize scheduler for periodic tasks
def init_scheduler():
    scheduler = BackgroundScheduler()

    # Fetch Reddit items daily at midnight
    scheduler.add_job(
        fetch_reddit_items,
        'cron',
        hour=0,
        minute=0
    )

    # Check prices for tracked items every 6 hours
    scheduler.add_job(
        check_prices_and_notify,
        'interval',
        hours=6
    )

    scheduler.start()


# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Welcome to the BuyItForLife Sale Tracker API",
        "docs": "/docs",
        "redoc": "/redoc"
    }


# Auth0 user information endpoint
@app.get("/api/user/me")
async def get_user_info(user=Depends(auth.get_user)):
    return {
        "id": user.get("sub"),
        "email": user.get("email"),
        "name": user.get("name", "Anonymous"),
        "picture": user.get("picture"),
        "scopes": user.get("scope", "").split(),
        "verified": user.get("email_verified", False)
    }


# Run the application
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)