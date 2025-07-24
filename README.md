# FastHTML + Polar.sh + Google Auth Setup Guide

## Overview

This FastHTML project is a minimal scaffold for GoogleAuth + Polar.sh products. The goal is to sell a product that can only be accessed by authorized users.

After you've setup your .env file from the instructions below, run: `uv run --env-file .env polar-min-app.py` to start

Use Stripe fake credit cards for purchasing: https://docs.stripe.com/testing

### User Flow

1. **Google Authenticate**
2. **Product page (`/product`)** - Check for active subscriptions
   - **If the user is not subscribed:**
     - Use buttons with `/create-checkout` route for purchases
   - **If the user is subscribed:**
     - Give them option to cancel (which does not immediately end subscription)
     - Give them option to upgrade/downgrade (based on price of available subscriptions & current active subscription)
     - Show them content only their subscription can see
     - There is option to "revoke", which is for testing purposes and should not be an option for a user

### Purchase Process

- `/create-checkout` route
- Creates checkout session with user_id (external_user_id to polar)
- Once complete, return to `/success` route
- Make sure `/success` isn't behind auth.. or polar won't be able to reach it (not sure this is being handled appropriately)


### Notes

- I do not save any information about the user *except* for a "user_id" which is passed to Polar as a "external_user_id"
- The advantage to this setup is I *never* have to worry about a user's status. I don't have to update any database and be concerned if a user is/is not subscribed
- I offload all of the user subscription management to Polar!

## Required Setup

### Polar Sandbox Account

1. Visit: https://sandbox.polar.sh/
2. Setup at least 1 subscription product

**Note:**
- All data & purchases in sandbox environment is fake
- Creating products can be done with the polar python SDK

### Local to HTTPS

1. Download ngrok
2. Run: `ngrok http 5001`
3. Record the resulting endpoint.. should look like (with a different prefix): `https://43mnsdm3knsf.ngrok-free.app/`

### Google Auth

1. Create Google Cloud Console account
2. Go to Google Auth Clients section (https://console.cloud.google.com/auth/clients)
3. Click: "+ Create client" → Select: "Web application" in Application Type dropdown → Fill in Authorized JavaScript Origin & Redirect URIs (See GoogleAuthClientRedirectExample.png in repo)
4. Copy Client ID & Client Secret to add to your `.env` file (see below)

### Setup Polar Webhook (optional)

1. Visit: https://sandbox.polar.sh/dashboard
2. On LHS NAV go to: Settings → Webhooks
3. Click: "Add Endpoint"
4. Input ngrok endpoint for "URL".. should look like (with a different prefix): `https://fdsasdf231cads.ngrok-free.app/`
5. Select "RAW" option in Format
6. Click some or all of the boxes
7. Copy the Webhook Secret Token of the endpoint you just created.. should look like: `"polar_whs_l6m4QN..."` and add it to your `.env` file (see below)

**Note:**
- This webhook capture is not required, but could be a useful feature if you want to record or parse events

### .env File

This project requires an `.env` file with the following values:

```env
NGROK_ENDPOINT=...

POLAR_ACCESS_TOKEN=...
POLAR_ORG_ID=...
POLAR_WEBHOOK_SECRET=...

AUTH_CLIENT_SECRET=...
AUTH_CLIENT_ID=...
```
Use the .env.example as a template to create the .env file. Do not commit your .env file to github!


**Note:**
- The polar access token can be found at the bottom of the Settings → General page on https://sandbox.polar.sh/dashboard/ under the "Developer" Section
- The polar success URL requires the ngrok endpoint to redirect after the checkout session