# Auth0 Setup Guide for BuyItForLife Sale Tracker

This guide walks you through setting up Auth0 for your BuyItForLife Sale Tracker application.

## 1. Create an Auth0 Account

If you don't already have an Auth0 account:

1. Go to [Auth0's website](https://auth0.com/) and sign up for a free account
2. Verify your email address

## 2. Create a New API

First, set up an API in Auth0 to represent your backend:

1. In the Auth0 dashboard, navigate to **Applications** → **APIs**
2. Click **Create API**
3. Fill in the form:
   - **Name**: BuyItForLife Sale Tracker API
   - **Identifier**: `https://api.buyitforlife-tracker.com` (this doesn't need to be a real URL, just a unique identifier)
   - **Signing Algorithm**: RS256 (default)
4. Click **Create**

## 3. Define API Permissions (Scopes)

Define the scopes (permissions) your API will use:

1. In your newly created API settings, go to the **Permissions** tab
2. Add the following permissions:
   - `read:items` - Read items from the BuyItForLife database
   - `write:items` - Create or update items in the BuyItForLife database
   - `read:alerts` - Read alert settings
   - `write:alerts` - Create or update alert settings
3. Click **Add** for each permission

## 4. Create a Single-Page Application

Next, create an application that represents your frontend:

1. Navigate to **Applications** → **Applications**
2. Click **Create Application**
3. Fill in the form:
   - **Name**: BuyItForLife Sale Tracker Frontend
   - **Application Type**: Single Page Web Applications
4. Click **Create**

## 5. Configure Your Application

In your application settings:

1. Go to the **Settings** tab
2. Set the following URLs:
   - **Allowed Callback URLs**: `http://localhost:3000/callback, https://yourdomain.com/callback`
   - **Allowed Logout URLs**: `http://localhost:3000, https://yourdomain.com`
   - **Allowed Web Origins**: `http://localhost:3000, https://yourdomain.com`
3. Scroll down and click **Save Changes**

## 6. Create a Machine-to-Machine Application (Optional)

If you need backend services to communicate with each other:

1. Navigate to **Applications** → **Applications**
2. Click **Create Application**
3. Fill in the form:
   - **Name**: BuyItForLife Backend Service
   - **Application Type**: Machine to Machine Applications
4. Select your API from the dropdown
5. Select the permissions this service will need
6. Click **Create**

## 7. Update Environment Variables

Update your `.env` file with the Auth0 configuration:

```
AUTH0_DOMAIN=your-tenant-name.auth0.com
AUTH0_API_AUDIENCE=https://api.buyitforlife-tracker.com
AUTH0_CLIENT_ID=your-spa-client-id
AUTH0_CLIENT_SECRET=