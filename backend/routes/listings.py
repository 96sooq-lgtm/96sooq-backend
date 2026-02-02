from fastapi import APIRouter, HTTPException, status, Depends, Query
from models import schemas
from db.supabase_client import db
from utils.auth import get_current_customer, get_current_admin
from typing import List, Optional

# Public/User Router
router = APIRouter(
    prefix="/api/listings",
    tags=["listings"]
)

# Admin Router
admin_router = APIRouter(
    prefix="/api/admin/listings",
    tags=["admin-listings"],
    dependencies=[Depends(get_current_admin)]
)


# -------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------
def is_leaf_category(category_id: str) -> bool:
    """Check if a category is a leaf node."""
    children = db.select("categories", filters={"parent_id": category_id})
    return not bool(children)

# -------------------------------------------------
# PUBLIC / CUSTOMER ENDPOINTS
# -------------------------------------------------

@router.post("/", response_model=schemas.ListingOut, status_code=status.HTTP_201_CREATED)
async def create_listing(
    payload: schemas.ListingCreate,
    current_user: dict = Depends(get_current_customer)
):
    """
    Create a new listing.
    
    Business Rules:
    - First listing is FREE
    - 2nd listing onwards requires payment (plan_id must be provided)
    - All listings require admin approval (status = pending_approval)
    - Category must be a leaf node
    - Store is optional
    """
    user_id = current_user["id"]
    
    # 1. Verify Leaf Category
    if not is_leaf_category(payload.category_id):
         raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Listings can only be added to leaf categories"
        )
    
    # 2. Check if this is user's first listing
    user_listings = db.select("listings", filters={"user_id": user_id})
    listing_count = len(user_listings) if user_listings else 0
    
    is_first_listing = listing_count == 0
    
    # 3. Enforce payment rule
    if not is_first_listing:
        # Not first listing - payment required
        if not payload.plan_id:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Payment required. This is not your first listing. Please select a pricing plan."
            )
        
        # Verify plan exists and is active
        plan = db.select_one("pricing_plans", payload.plan_id)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pricing plan not found"
            )
        
        if not plan.get("is_active", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected pricing plan is not active"
            )
        
        # TODO: Here you would integrate payment gateway
        # For now, we assume payment is successful if plan_id is provided
    else:
        # First listing is free - no plan needed
        pass
    
    # 4. Prepare Data
    data = payload.dict(exclude={"images"})
    data["user_id"] = user_id
    data["status"] = "pending_approval"  # ALL listings require admin approval
    
    # If free listing, ensure plan_id is None
    if is_first_listing and not payload.plan_id:
        data["plan_id"] = None
        data["plan_expires_at"] = None
    
    # 5. Create Listing
    listing = db.insert("listings", data)
    if not listing:
        raise HTTPException(status_code=500, detail="Failed to create listing")
        
    listing_id = listing["id"]
    
    # 6. Handle Images (MVP: Simple Insert Loop)
    if payload.images:
        for idx, img_url in enumerate(payload.images):
            db.insert("listing_images", {
                "listing_id": listing_id,
                "image_url": img_url,
                "is_main": (idx == 0),
                "display_order": idx
            })
            
    return listing


@router.get("/", response_model=List[schemas.ListingOut])
async def list_listings(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    category_id: Optional[str] = None,
    store_id: Optional[str] = None,
    search: Optional[str] = None
):
    """
    List active listings with filters.
    """
    def query_func(table):
        query = table.select("*").eq("status", "active")
        
        if category_id:
            query = query.eq("category_id", category_id)
        if store_id:
            query = query.eq("store_id", store_id)
        if search:
            # Supabase/PostgREST text search (simple ilike for title)
            query = query.ilike("title", f"%{search}%")
            
        return query.range(skip, skip + limit - 1).order("created_at", desc=True)

    result = db.query("listings", query_func)
    return result.data if result.data else []


@router.get("/{listing_id}", response_model=schemas.ListingOut)
async def get_listing(listing_id: str):
    listing = db.select_one("listings", listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing


@router.put("/{listing_id}", response_model=schemas.ListingOut)
async def update_listing(
    listing_id: str, 
    payload: schemas.ListingUpdate,
    current_user: dict = Depends(get_current_customer)
):
    # Verify ownership
    listing = db.select_one("listings", listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
        
    if listing["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to update this listing")
        
    update_data = payload.dict(exclude_unset=True)
    # Block status update
    if "status" in update_data:
        del update_data["status"]
        
    updated = db.update("listings", listing_id, update_data)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update listing")
        
    return updated



# -------------------------------------------------
# ADMIN ENDPOINTS
# -------------------------------------------------

@admin_router.get("/", response_model=List[schemas.ListingOut])
async def list_all_listings_admin(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None
):
    """
    Admin: List all listings with optional status filter.
    Used for approval management in admin panel.
    """
    def query_func(table):
        query = table.select("*")
        
        if status:
            query = query.eq("status", status)
            
        return query.range(skip, skip + limit - 1).order("created_at", desc=True)

    result = db.query("listings", query_func)
    return result.data if result.data else []


@admin_router.put("/{listing_id}/approve")
async def approve_listing(listing_id: str):
    updated = db.update("listings", listing_id, {"status": "active"})
    if not updated:
         raise HTTPException(status_code=404, detail="Listing not found or update failed")
    return updated

@admin_router.put("/{listing_id}/reject")
async def reject_listing(listing_id: str, reason: str = Query(..., min_length=1)):
    updated = db.update("listings", listing_id, {"status": "rejected", "rejection_reason": reason})
    if not updated:
         raise HTTPException(status_code=404, detail="Listing not found or update failed")
    return updated

