from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional
from models.schemas import PricingPlanCreate, PricingPlanOut
from db.supabase_client import db
from utils.auth import get_current_admin
from uuid import uuid4

# Admin Router
admin_router = APIRouter(
    prefix="/api/admin/subscriptions",
    tags=["Admin Subscriptions"]
)

# User Router
user_router = APIRouter(
    prefix="/api/subscriptions",
    tags=["Subscriptions"]
)

# ----------------------------------------------------------------
# ADMIN ENDPOINTS
# ----------------------------------------------------------------

@admin_router.post("/", response_model=PricingPlanOut, status_code=status.HTTP_201_CREATED)
async def create_subscription_plan(plan: PricingPlanCreate, admin: dict = Depends(get_current_admin)):
    """
    Create a new subscription plan (Admin only)
    """
    plan_data = plan.dict()
    
    # Validate type
    if plan_data['type'] not in ['listing', 'ad', 'offer']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid plan type. Must be 'listing', 'ad', or 'offer'"
        )

    # Insert into DB
    try:
        new_plan = db.insert("pricing_plans", plan_data)
        if not new_plan:
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create plan")
        return new_plan
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@admin_router.get("/", response_model=List[PricingPlanOut])
async def list_subscription_plans(admin: dict = Depends(get_current_admin)):
    """
    List all subscription plans (Admin only)
    """
    try:
        plans = db.select("pricing_plans")
        return plans
    except Exception as e:
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@admin_router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription_plan(plan_id: str, admin: dict = Depends(get_current_admin)):
    """
    Delete a subscription plan (Admin only)
    """
    # Check if exists
    existing = db.select_one("pricing_plans", plan_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
        
    # Delete
    success = db.delete("pricing_plans", plan_id)
    if not success:
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete plan")

# ----------------------------------------------------------------
# USER ENDPOINTS
# ----------------------------------------------------------------

@user_router.get("/listing-prices", response_model=List[PricingPlanOut])
async def get_listing_prices():
    """
    Get all active subscription plans for Listings
    """
    try:
        # Filter by type='listing' and is_active=True
        # Supabase select method supports basic filters. 
        # For multiple filters we might need to use the query method or filter manually if select is limited.
        # Based on supabase_client.py, it supports a dictionary of filters.
        filters = {"type": "listing", "is_active": True}
        plans = db.select("pricing_plans", filters=filters)
        return plans
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@user_router.get("/ad-prices", response_model=List[PricingPlanOut])
async def get_ad_prices():
    """
    Get all active subscription plans for Ads
    """
    try:
        filters = {"type": "ad", "is_active": True}
        plans = db.select("pricing_plans", filters=filters)
        return plans
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@user_router.get("/offer-listing-prices", response_model=List[PricingPlanOut])
async def get_offer_prices():
    """
    Get all active subscription plans for Offers
    """
    try:
        filters = {"type": "offer", "is_active": True}
        plans = db.select("pricing_plans", filters=filters)
        return plans
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
