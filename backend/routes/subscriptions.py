from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List, Optional
from models import schemas
from models.schemas import PricingPlanCreate, PricingPlanOut
from db.supabase_client import db
from utils.auth import get_current_admin
from uuid import uuid4
from datetime import datetime, timedelta
from utils.auth import get_current_customer

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
# HELPER FUNCTIONS
# ----------------------------------------------------------------
async def check_listing_quota(user_id: str, is_store_owner: bool) -> dict:
    """
    Check listing quota for the current month.
    Returns:
    {
        "can_create_free": bool,
        "can_create_paid": bool,
        "free_remaining": int,
        "paid_remaining": int (or -1 if unlimited),
        "message": str
    }
    """
    # 1. Get current month range
    now = datetime.utcnow()
    start_of_month = datetime(now.year, now.month, 1)
    # End of month is start of next month
    if now.month == 12:
        start_of_next_month = datetime(now.year + 1, 1, 1)
    else:
        start_of_next_month = datetime(now.year, now.month + 1, 1)
        
    start_str = start_of_month.isoformat()
    end_str = start_of_next_month.isoformat()
    
    # 2. Count active listings created in this month
    # Note: We need a complex query to filter by created_at >= start and < end
    # Supabase simple client might need a custom query func
    def query_count(table):
        return table.select("id", count="exact")\
            .eq("user_id", user_id)\
            .gte("created_at", start_str)\
            .lt("created_at", end_str)
            
    result = db.query("listings", query_count)
    count = result.count if result.count is not None else 0
    
    # 3. Define Limits
    # Individual: 1 Free, 5 Paid (Total 6?) Or 1 Free AND 5 Paid?
    # Requirement: "free 1 listing per month, certain amount - 5 listings/ month"
    # Logic: 
    # If count == 0 -> Can create Free OR Paid
    # If count >= 1 -> Can create Paid only (up to limit)
    
    FREE_LIMIT = 1
    
    if is_store_owner:
        PAID_LIMIT = -1 # Unlimited
    else:
        PAID_LIMIT = 5 # Individual limit for paid listings
        
    can_create_free = count < FREE_LIMIT
    
    if PAID_LIMIT == -1:
        can_create_paid = True
        paid_remaining = -1
    else:
        # Total allowed = Free + Paid limits? Or just total count?
        # Let's assume Total Count Limit for individual is 1 + 5 = 6
        TOTAL_LIMIT = FREE_LIMIT + PAID_LIMIT
        can_create_paid = count < TOTAL_LIMIT
        paid_remaining = max(0, TOTAL_LIMIT - count)
        
    return {
        "can_create_free": can_create_free,
        "can_create_paid": can_create_paid,
        "usage": count,
        "paid_remaining": paid_remaining
    }

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
async def list_subscription_plans(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    admin: dict = Depends(get_current_admin)
):
    """
    List all subscription plans (Admin only) with pagination.
    """
    def query_func(table):
        return table.select("*").range(skip, skip + limit - 1).order("created_at", desc=True)

    result = db.query("pricing_plans", query_func)
    return result.data if result.data else []

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
# USER SUBSCRIPTION ENDPOINTS (Manage Purchases)
# ----------------------------------------------------------------

@user_router.post("/purchase", response_model=schemas.UserSubscriptionOut)
async def purchase_subscription(
    payload: schemas.UserSubscriptionCreate,
    current_user: dict = Depends(get_current_customer)
):
    """
    Purchase a subscription plan.
    - Sets remaining_quota based on plan.
    - Sets end_date based on plan duration.
    """
    plan = db.select_one("pricing_plans", payload.plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
        
    duration_days = plan.get("duration_days", 30)
    quota = plan.get("quota", 0) # -1 for unlimited
    
    # Calculate dates
    start_date = datetime.utcnow()
    end_date = start_date + timedelta(days=duration_days)
    
    # Create subscription
    sub_data = {
        "user_id": current_user["id"],
        "plan_id": payload.plan_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "remaining_quota": quota,
        "status": "active"
    }
    
    subscription = db.insert("user_subscriptions", sub_data)
    if not subscription:
        raise HTTPException(status_code=500, detail="Failed to create subscription")
        
    # Attach plan details for response
    subscription["plan_details"] = plan
    return subscription

@user_router.get("/my-subscription", response_model=List[schemas.UserSubscriptionOut])
async def get_my_subscriptions(
    current_user: dict = Depends(get_current_customer)
):
    """
    Get all subscriptions for the current user.
    """
    subs = db.select("user_subscriptions", filters={"user_id": current_user["id"]})
    
    # Enrich with plan details
    for sub in subs:
        plan = db.select_one("pricing_plans", sub["plan_id"])
        if plan:
            sub["plan_details"] = plan
            
    return subs if subs else []


# ----------------------------------------------------------------
# USER ENDPOINTS
# ----------------------------------------------------------------

@user_router.get("/listing-prices")
async def get_listing_prices(
    is_store: bool = Query(False, description="Is request for a store listing?"),
    current_user: dict = Depends(get_current_customer)
):
    """
    Get eligible subscription plans for Listings based on user's quota.
    """
    try:
        user_id = current_user["id"]
        # Check quota
        quota_status = await check_listing_quota(user_id, is_store)
        
        filters = {"type": "listing", "is_active": True}
        
        # Filter by target audience
        target = "store" if is_store else "individual"
        filters["target_audience"] = target
        
        plans = db.select("pricing_plans", filters=filters)
        
        # Filter plans based on quota
        # If cannot create free, remove free plans (price == 0)
        # If cannot create paid, remove paid plans? (price > 0)
        
        eligible_plans = []
        for plan in plans:
            price = plan.get("price", 0)
            
            if price == 0:
                if quota_status["can_create_free"]:
                    eligible_plans.append(plan)
            else:
                if quota_status["can_create_paid"]:
                    eligible_plans.append(plan)
                    
        return {
            "quota_status": quota_status,
            "plans": eligible_plans
        }
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
