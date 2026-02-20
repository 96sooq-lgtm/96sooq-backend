from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from models import schemas
from db.supabase_client import db
from utils.auth import get_current_admin, get_current_customer
from datetime import datetime, timedelta

# Public/User Router
router = APIRouter(
    prefix="/api/banners",
    tags=["banners"]
)

# Admin Router
admin_router = APIRouter(
    prefix="/api/admin/banners",
    tags=["admin-banners"],
    dependencies=[Depends(get_current_admin)]
)

# -------------------------------------------------
# PUBLIC / CUSTOMER ENDPOINTS
# -------------------------------------------------

@router.post("/boost", response_model=schemas.AdBannerOut, status_code=status.HTTP_201_CREATED)
async def boost_listing(
    payload: schemas.UserBoostCreate,
    current_user: dict = Depends(get_current_customer)
):
    """
    User boosts their own listing as an ad.
    - Only requires: listing_id, type, description (optional)
    - user_id is taken from JWT token
    - name and image_url are auto-derived from the listing
    """
    try:
        user_id = current_user["id"]

        # Verify listing exists and belongs to the user
        listing = db.select_one("listings", payload.listing_id)
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")

        if listing["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="You can only boost your own listings")

        # Auto-derive name from listing title
        name = listing.get("title", "Boosted Listing")

        # Auto-derive image from listing's first image (if available)
        images = listing.get("images") or []
        image_url = images[0] if images else None

        # Determine status based on listing state
        banner_status = "active" if listing.get("status") == "active" else "pending_approval"

        data = {
            "user_id": user_id,
            "listing_id": payload.listing_id,
            "type": payload.type,
            "name": name,
            "image_url": image_url,
            "description": payload.description,
            "status": banner_status,
        }

        # If plan_id provided, attach it and calculate expiry immediately
        if payload.plan_id:
            plan = db.select_one("pricing_plans", payload.plan_id)
            if not plan:
                raise HTTPException(status_code=404, detail="Plan not found")
            data["plan_id"] = payload.plan_id
            duration = plan.get("duration_days", 7)
            data["expires_at"] = (datetime.utcnow() + timedelta(days=duration)).isoformat()

        banner = db.insert("ad_banners", data)
        if not banner:
            raise HTTPException(status_code=500, detail="Failed to create boost")

        return banner


    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{banner_id}/pay", response_model=schemas.AdBannerOut)
async def pay_for_banner(
    banner_id: str,
    plan_id: str
):
    """
    Step 2: User selects plan and pays.
    Updates status to 'pending_approval'.
    """
    banner = db.select_one("ad_banners", banner_id)
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")

    plan = db.select_one("pricing_plans", plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    updated = db.update("ad_banners", banner_id, {
        "plan_id": plan_id,
        "status": "pending_approval",
    })

    if not updated:
        raise HTTPException(status_code=500, detail="Payment verification failed")

    return updated

@router.get("/my-banners", response_model=List[schemas.AdBannerOut])
async def list_my_banners(
    current_user: dict = Depends(get_current_customer)
):
    """
    List logged-in user's banners.
    """
    banners = db.select("ad_banners", filters={"user_id": current_user["id"]})
    return banners if banners else []

@router.get("/public", response_model=List[schemas.AdBannerOut])
async def list_active_banners(
    type: Optional[str] = None,
    limit: int = 20
):
    """
    Public endpoint to fetch active banners for display in the app.
    """
    def query_func(table):
        query = table.select("*").eq("status", "active")
        if type:
            query = query.eq("type", type)
        return query.limit(limit).order("created_at", desc=True)

    result = db.query("ad_banners", query_func)
    return result.data if result.data else []


@router.get("/home", response_model=List[schemas.AdBannerOut])
async def get_home_banners(
    limit: int = Query(20, ge=1, le=100)
):
    """
    Public home page banners — no auth required.
    Returns only admin-created active banners (no listing_id),
    ordered by newest first. Frontend can display as a sliding carousel.
    """
    def query_func(table):
        return (
            table.select("*")
            .eq("status", "active")
            .is_("listing_id", "null")   # admin banners only (no listing_id)
            .limit(limit)
            .order("created_at", desc=True)
        )

    result = db.query("ad_banners", query_func)
    return result.data if result.data else []


# -------------------------------------------------
# ADMIN ENDPOINTS
# -------------------------------------------------

@admin_router.post("/", response_model=schemas.AdBannerOut, status_code=status.HTTP_201_CREATED)
async def create_banner_admin(
    payload: schemas.AdminBannerCreate,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Admin: Create a system banner directly (status=active, expires in 30 days).
    No user_id or plan_id required — admin banners are always active.
    """
    try:
        data = {
            "name": payload.name,
            "type": payload.type,
            "image_url": payload.image_url,
            "link_url": payload.link_url,
            "description": payload.description,
            # No user_id — admins are not in app_users; admin banners are system-level
            "status": "active",
            "duration_days": payload.duration_days,
            "expires_at": (datetime.utcnow() + timedelta(days=payload.duration_days)).isoformat(),
        }

        banner = db.insert("ad_banners", data)
        if not banner:
            raise HTTPException(status_code=500, detail="Failed to create banner")

        return banner

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/", response_model=List[schemas.AdBannerOut])
async def list_all_banners_admin(
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Admin: List all banners with pagination and filters.
    """
    def query_func(table):
        query = table.select("*")
        if status:
            query = query.eq("status", status)
        return query.range(skip, skip + limit - 1).order("created_at", desc=True)
        
    result = db.query("ad_banners", query_func)
    return result.data if result.data else []

@admin_router.patch("/{banner_id}", response_model=schemas.AdBannerOut)
async def update_banner_admin(
    banner_id: str,
    payload: schemas.AdBannerUpdate,
):
    """
    Admin: Partially update a banner.
    Only fields provided in the request body will be updated.
    If duration_days is updated, expires_at is recalculated from now.
    """
    banner = db.select_one("ad_banners", banner_id)
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")

    updates = payload.dict(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Recalculate expiry if duration_days changed
    if "duration_days" in updates:
        updates["expires_at"] = (
            datetime.utcnow() + timedelta(days=updates["duration_days"])
        ).isoformat()

    updated = db.update("ad_banners", banner_id, updates)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update banner")

    return updated


@admin_router.put("/{banner_id}/approve", response_model=schemas.AdBannerOut)
async def approve_banner(banner_id: str):
    """
    Approve a banner. Calculate expiration based on plan.
    """
    banner = db.select_one("ad_banners", banner_id)
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")
        
    if not banner.get("plan_id"):
         raise HTTPException(status_code=400, detail="Banner has no plan associated")
         
    plan = db.select_one("pricing_plans", banner["plan_id"])
    if not plan:
        # Fallback if plan deleted? Or error?
        duration = 30 # Default 30 days
    else:
        duration = plan.get("duration_days", 30)
        
    expires_at = datetime.utcnow() + timedelta(days=duration)
    
    updated = db.update("ad_banners", banner_id, {
        "status": "active",
        "expires_at": expires_at.isoformat()
    })
    
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to approve banner")
        
    return updated

@admin_router.put("/{banner_id}/reject", response_model=schemas.AdBannerOut)
async def reject_banner(banner_id: str):
    updated = db.update("ad_banners", banner_id, {"status": "rejected"})
    if not updated:
         raise HTTPException(status_code=404, detail="Banner not found")
    return updated

@admin_router.delete("/{banner_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_banner(banner_id: str):
    success = db.delete("ad_banners", banner_id)
    if not success:
         raise HTTPException(status_code=404, detail="Banner not found")
