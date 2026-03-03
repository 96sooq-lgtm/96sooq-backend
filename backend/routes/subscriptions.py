from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List, Optional
from models import schemas
from models.schemas import PricingPlanCreate, PricingPlanOut, PricingPlanUpdate
from db.supabase_client import db
from utils.logger import get_logger

logger = get_logger(__name__)
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
    Check listing quota based on active subscription.
    No free tier — all listings require a paid plan.
    Returns:
    {
        "has_active_subscription": bool,
        "can_create": bool,
        "remaining_quota": int (or -1 if unlimited),
        "usage_this_month": int
    }
    """
    now = datetime.utcnow()

    # 1. Count listings this month
    start_of_month = datetime(now.year, now.month, 1)
    if now.month == 12:
        start_of_next_month = datetime(now.year + 1, 1, 1)
    else:
        start_of_next_month = datetime(now.year, now.month + 1, 1)

    def query_count(table):
        return table.select("id", count="exact")\
            .eq("user_id", user_id)\
            .gte("created_at", start_of_month.isoformat())\
            .lt("created_at", start_of_next_month.isoformat())

    result = db.query("listings", query_count)
    usage = result.count if result.count is not None else 0

    # 2. Check active subscription
    def sub_query(table):
        return table.select("*")\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .gte("end_date", now.isoformat())\
            .order("end_date", desc=True)\
            .limit(1)

    sub_result = db.query("user_subscriptions", sub_query)
    active_sub = sub_result.data[0] if sub_result.data else None

    if not active_sub:
        return {
            "has_active_subscription": False,
            "can_create": False,
            "remaining_quota": 0,
            "usage_this_month": usage,
            "message": "No active subscription. Please purchase a plan to create listings."
        }

    remaining = active_sub.get("remaining_quota", 0)

    # Store owners with unlimited plans
    if is_store_owner and remaining == -1:
        return {
            "has_active_subscription": True,
            "can_create": True,
            "remaining_quota": -1,
            "usage_this_month": usage
        }

    return {
        "has_active_subscription": True,
        "can_create": remaining > 0,
        "remaining_quota": remaining,
        "usage_this_month": usage
    }

# ----------------------------------------------------------------
# ADMIN ENDPOINTS
# ----------------------------------------------------------------

@admin_router.post("/", response_model=PricingPlanOut, status_code=status.HTTP_201_CREATED)
async def create_subscription_plan(plan: PricingPlanCreate, admin: dict = Depends(get_current_admin)):
    """
    Create a new subscription plan (Admin only).
    For ad plans, specify ad_sub_type: 'product_listing', 'chat_screen', or 'offers'.
    """
    plan_data = plan.dict()

    # Validate type
    valid_types = ['listing', 'ad', 'offer']
    if plan_data['type'] not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan type. Must be one of: {valid_types}"
        )

    # Validate ad_sub_type when type is 'ad'
    valid_ad_sub_types = ['product_listing', 'chat_screen', 'offers']
    if plan_data['type'] == 'ad':
        if not plan_data.get('ad_sub_type'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"ad_sub_type is required when type is 'ad'. Must be one of: {valid_ad_sub_types}"
            )
        if plan_data['ad_sub_type'] not in valid_ad_sub_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid ad_sub_type. Must be one of: {valid_ad_sub_types}"
            )
    else:
        # Clear ad_sub_type for non-ad plans
        plan_data['ad_sub_type'] = None

    # Validate target_audience
    valid_audiences = ['individual', 'store', 'everyone']
    if plan_data.get('target_audience') not in valid_audiences:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid target_audience. Must be one of: {valid_audiences}"
        )

    try:
        logger.info(f"Creating plan: name='{plan_data['name_en']}', type={plan_data['type']}, ad_sub_type={plan_data.get('ad_sub_type')}")
        new_plan = db.insert("pricing_plans", plan_data)
        if not new_plan:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create plan")
        logger.info(f"Plan created: id={new_plan['id']}, name='{new_plan['name_en']}'")
        return new_plan
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating plan: {type(e).__name__}: {e}", exc_info=True)
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

@admin_router.delete("/{plan_id}", status_code=status.HTTP_200_OK)
async def delete_subscription_plan(plan_id: str, admin: dict = Depends(get_current_admin)):
    """
    Delete a subscription plan (Admin only)
    """
    try:
        existing = db.select_one("pricing_plans", plan_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

        # Check if any user subscriptions reference this plan (FK constraint guard)
        linked_subs = db.select("user_subscriptions", filters={"plan_id": plan_id})
        if linked_subs:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot delete: {len(linked_subs)} active subscription(s) reference this plan. Deactivate the plan instead."
            )

        success = db.delete("pricing_plans", plan_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete plan")

        return {"message": "Plan deleted successfully", "id": plan_id}

    except HTTPException:
        raise
    except Exception as e:
        err = str(e)
        # Detect PostgreSQL FK violation (error code 23503)
        if "23503" in err or "foreign key" in err.lower() or "violates foreign key" in err.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This plan cannot be deleted because it is referenced by existing subscriptions or payments. Please deactivate it instead."
            )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=err)




@admin_router.patch("/{plan_id}", response_model=PricingPlanOut)
async def update_subscription_plan(
    plan_id: str,
    payload: PricingPlanUpdate,
    admin: dict = Depends(get_current_admin)
):
    """
    Partially update a subscription plan (Admin only).
    Useful for toggling is_best_value, is_active, price, etc.
    """
    existing = db.select_one("pricing_plans", plan_id)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    # Only send fields that were explicitly provided
    updates = payload.dict(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields provided to update")

    try:
        def query_func(table):
            return table.update(updates).eq("id", plan_id)

        result = db.query("pricing_plans", query_func)
        updated = result.data[0] if result.data else None
        if not updated:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update plan")
        return updated
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

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
    # Prevent duplicate purchase of unlimited plans
    if quota == -1:
        now_iso = datetime.utcnow().isoformat()
        active_sub = db.select("user_subscriptions", filters={
            "user_id": current_user["id"],
            "plan_id": payload.plan_id,
            "status": "active"
        })
        # Check if dates overlap
        if active_sub and any((sub.get("end_date") or "") > now_iso for sub in active_sub):
            raise HTTPException(status_code=400, detail="You already have an active subscription for this unlimited plan.")
    
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
    Get eligible paid subscription plans for listings.
    No free plans are available.
    """
    try:
        user_id = current_user["id"]
        quota_status = await check_listing_quota(user_id, is_store)

        target = "store" if is_store else "individual"

        def query_func(table):
            return (
                table.select("*")
                .eq("type", "listing")
                .eq("is_active", True)
                .gt("price", 0)  # Only paid plans
                .in_("target_audience", [target, "everyone"])
            )

        result = db.query("pricing_plans", query_func)
        plans = result.data if result.data else []

        return {
            "quota_status": quota_status,
            "plans": plans
        }
    except Exception as e:
        logger.error(f"Error fetching listing prices: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@user_router.get("/ad-prices", response_model=List[PricingPlanOut])
async def get_ad_prices(
    is_store: bool = Query(False, description="Is request for a store user?"),
    ad_sub_type: Optional[str] = Query(None, description="Filter by ad sub-type: 'product_listing', 'chat_screen', or 'offers'"),
    current_user: dict = Depends(get_current_customer)
):
    """
    Get all active ad plans.
    Filters by the user's role (store vs individual) and optionally by ad_sub_type.
    """
    try:
        user_id = current_user["id"]
        target = "store" if is_store else "individual"

        def query_func(table):
            query = (
                table.select("*")
                .eq("type", "ad")
                .eq("is_active", True)
                .in_("target_audience", [target, "everyone"])
            )
            if ad_sub_type:
                query = query.eq("ad_sub_type", ad_sub_type)
            return query

        result = db.query("pricing_plans", query_func)
        return result.data if result.data else []
    except Exception as e:
        logger.error(f"Error fetching ad prices: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@user_router.get("/offer-listing-prices", response_model=List[PricingPlanOut])
async def get_offer_prices():
    """
    Get all active subscription plans for Offers.
    """
    try:
        filters = {"type": "offer", "is_active": True}
        plans = db.select("pricing_plans", filters=filters)
        return plans
    except Exception as e:
        logger.error(f"Error fetching offer prices: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
