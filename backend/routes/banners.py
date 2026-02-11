from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from models import schemas
from db.supabase_client import db
from utils.auth import get_current_admin
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

@router.post("/", response_model=schemas.AdBannerOut, status_code=status.HTTP_201_CREATED)
async def create_banner(
    payload: schemas.AdBannerCreate
):
    """
    Step 1: User creates a banner draft.
    Status starts as 'pending_payment'.
    """
    data = payload.dict()
    # user_id is now in payload
    data["status"] = "pending_payment"
    
    # If plan_id is provided during creation, we might skip to pending_approval if payment is handled check
    # But usually creation is step 1.
    if data.get("plan_id"):
        # Verify plan exists
        plan = db.select_one("pricing_plans", data["plan_id"])
        if not plan:
             raise HTTPException(status_code=400, detail="Invalid plan_id")
             
        # Simulate payment success for now
        data["status"] = "pending_approval"
    
    banner = db.insert("ad_banners", data)
    if not banner:
        raise HTTPException(status_code=500, detail="Failed to create banner")
        
    return banner

@router.put("/{banner_id}/pay", response_model=schemas.AdBannerOut)
async def pay_for_banner(
    banner_id: str,
    plan_id: str
):
    """
    Step 2: User selects plan and pays.
    Updates status to 'pending_approval'.
    """
    # Verify ownership
    banner = db.select_one("ad_banners", banner_id)
    if not banner:
        raise HTTPException(status_code=404, detail="Banner not found")
        
    # Since we removed auth, we skip checking user_id match for now
    # In a real app without auth, we might verify using some other way or just allow any valid banner_id update
    # or require user_id in params to match
        
    # Verify plan
    plan = db.select_one("pricing_plans", plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
        
    # Update banner
    updated = db.update("ad_banners", banner_id, {
        "plan_id": plan_id,
        "status": "pending_approval",
        # We could set expires_at here or upon approval. Usually upon approval.
    })
    
    if not updated:
        raise HTTPException(status_code=500, detail="Payment verification failed")
        
    return updated

@router.get("/my-banners", response_model=List[schemas.AdBannerOut])
async def list_my_banners(
    user_id: str = Query(..., description="User ID to fetch banners for")
):
    """
    List logged-in user's banners.
    """
    banners = db.select("ad_banners", filters={"user_id": user_id})
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


# -------------------------------------------------
# ADMIN ENDPOINTS
# -------------------------------------------------

@admin_router.post("/", response_model=schemas.AdBannerOut, status_code=status.HTTP_201_CREATED)
async def create_banner_admin(
    payload: schemas.AdBannerCreate,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Admin: Create a banner directly (status=active).
    """
    data = payload.dict()
    # Ensure user_id is set (payload has it, or we could override with admin's ID if payload.user_id is generic)
    # Since payload.user_id is required, we use it.
    
    data["status"] = "active"
    
    # Calculate expiration if plan_id is provided, otherwise default 30 days
    if data.get("plan_id"):
        plan = db.select_one("pricing_plans", data["plan_id"])
        if plan:
            duration = plan.get("duration_days", 30)
            data["expires_at"] = (datetime.utcnow() + timedelta(days=duration)).isoformat()
    else:
        # Default 30 days if no plan
        data["expires_at"] = (datetime.utcnow() + timedelta(days=30)).isoformat()
    
    banner = db.insert("ad_banners", data)
    if not banner:
        raise HTTPException(status_code=500, detail="Failed to create banner")
        
    return banner

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
