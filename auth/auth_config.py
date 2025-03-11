# app/auth/auth_config.py - Auth0 configuration and utilities
from fastapi import Depends, HTTPException, status
from fastapi_auth0 import Auth0, Auth0User
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Auth0 Configuration
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_API_AUDIENCE = os.getenv("AUTH0_API_AUDIENCE")
AUTH0_ALGORITHMS = ["RS256"]

# Initialize Auth0
auth = Auth0(domain=AUTH0_DOMAIN, api_audience=AUTH0_API_AUDIENCE, scopes={
    'read:items': 'Read items from the BuyItForLife database',
    'write:items': 'Create or update items in the BuyItForLife database',
    'read:alerts': 'Read alert settings',
    'write:alerts': 'Create or update alert settings'
})


# Permission checking
def require_user(user: Auth0User = Depends(auth.get_user)):
    """Validate the user is authenticated"""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return user


def require_scope(required_scope: str, user: Auth0User = Depends(auth.get_user)):
    """Validate that the user has the required scope"""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    token_scopes = user.get("scope", "").split()
    if required_scope not in token_scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required scope: {required_scope}"
        )

    return user


# Function to get Auth0 user profile ID
def get_user_id(user: Auth0User):
    """Get the user's unique identifier from Auth0"""
    return user.get('sub')


# Function to get user email
def get_user_email(user: Auth0User):
    """Get the user's email from Auth0"""
    return user.get('email')