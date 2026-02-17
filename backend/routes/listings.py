from fastapi import APIRouter, HTTPException, status, Depends, Query
from models import schemas
from db.supabase_client import db
from utils.auth import get_current_customer, get_current_admin
from utils.storage import s3_client
from typing import List, Optional
from datetime import datetime

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

def get_viewable_image_url(image_url_or_path: Optional[str]) -> Optional[str]:
    """
    Convert image URL or file path to a viewable URL.
    - If it's already a full URL (http/https), return as-is
    - If it's a file_path (starts with folder name), generate presigned URL
    """
    if not image_url_or_path:
        return None
    
    # If it's already a full URL, return as-is
    if image_url_or_path.startswith(('http://', 'https://')):
        return image_url_or_path
    
    # If it's a file_path, generate presigned URL for viewing
    if s3_client:
        presigned_url = s3_client.generate_presigned_url(image_url_or_path, expiration=3600)
        return presigned_url if presigned_url else image_url_or_path
    
    return image_url_or_path

def get_listing_images(listing_id: str) -> List[dict]:
    """Fetch listing images and make URLs viewable."""
    images = db.select("listing_images", filters={"listing_id": listing_id})
    if not images:
        return []
    
    # Sort by display_order
    images = sorted(images, key=lambda x: x.get("display_order", 0))
    
    # Make all image URLs viewable
    for img in images:
        if img.get("image_url"):
            img["image_url"] = get_viewable_image_url(img["image_url"])
    
    return images

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
    
    # 2. Check if user is a Store User
    user_stores = db.select("stores", filters={"user_id": user_id, "status": "active"})
    is_store_user = len(user_stores) > 0
    store_id = user_stores[0]["id"] if is_store_user else None
    
    # 3. Verify Location (City)
    location_id = payload.city
    if location_id:
        location = db.select_one("locations", location_id)
        if not location:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid city (location_id)"
            )

    # 4. Verify Condition
    if payload.condition not in ['new', 'used']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Condition must be 'new' or 'used'"
        )

    # 4. Enforce payment/quota rule (For Individual Users Only)
    # Store users follow Store Plan limits (Not implemented in detail here, assumed unlimited or managed elsewhere)
    if not is_store_user:
        # Check if this is user's first listing (Individual)
        user_listings = db.select("listings", filters={"user_id": user_id, "store_id": None})
        listing_count = len(user_listings) if user_listings else 0
        is_first_listing = listing_count == 0
        
        if not is_first_listing:
            # Check for active subscription
            # ... (Same logic as before)
            now = datetime.utcnow().isoformat()
            subs = db.select("user_subscriptions", filters={
                "user_id": user_id,
                "status": "active"
            })
            
            valid_sub = None
            for sub in subs:
                # Check expiry
                if sub["end_date"] > now:
                    # Check quota
                    q = sub.get("remaining_quota", 0)
                    if q == -1 or q > 0:
                        valid_sub = sub
                        break
            
            if not valid_sub:
                 raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail="No active subscription found. Please purchase a plan to create more listings."
                )
                
            # Deduct quota if not unlimited
            if valid_sub["remaining_quota"] != -1:
                new_quota = valid_sub["remaining_quota"] - 1
                db.update("user_subscriptions", valid_sub["id"], {"remaining_quota": new_quota})
    
    # 5. Prepare Data
    data = payload.dict(exclude={"images", "city"}) # Exclude city from payload, mapped to location_id
    data["user_id"] = user_id
    data["location_id"] = location_id
    data["status"] = "pending_approval"
    
    # Force store_id if store user
    if is_store_user:
        data["store_id"] = store_id
        # Plan logic for Store Listings? currently open/unlimited or bound to store plan expiry?
        # Leaving as-is for now.
    else:
        # User Listing
        data["store_id"] = None
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
    location_id: Optional[str] = None,
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
        if location_id:
            query = query.eq("location_id", location_id)
        if search:
            # Supabase/PostgREST text search (simple ilike for title)
            query = query.ilike("title", f"%{search}%")
            
        return query.range(skip, skip + limit - 1).order("created_at", desc=True)

    result = db.query("listings", query_func)
    listings = result.data if result.data else []
    
    # Add viewable images and location details
    for listing in listings:
        listing["images"] = get_listing_images(listing["id"])
        
        if listing.get("location_id"):
            loc = db.select_one("locations", listing["location_id"])
            if loc:
                listing["location_details"] = loc

    return listings


@router.get("/{listing_id}", response_model=schemas.ListingOut)
async def get_listing(listing_id: str):
    listing = db.select_one("listings", listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    # Add viewable images for e-commerce display
    listing["images"] = get_listing_images(listing_id)
    
    if listing.get("location_id"):
        loc = db.select_one("locations", listing["location_id"])
        if loc:
             listing["location_details"] = loc
    
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
    # Block status update from user
    if "status" in update_data:
        del update_data["status"]
        
    # Security/Loophole Fix:
    # If user edits an active listing (title, description, price, images, attributes),
    # we must revert status to 'pending_approval' to prevent content swapping.
    # Exception: Maybe location or minor fields? But generally safer to re-approve.
    
    # Check if any sensitive fields are being updated
    sensitive_fields = ["title", "description", "price", "images", "attributes_values", "category_id"]
    is_sensitive_update = any(field in update_data for field in sensitive_fields)
    
    if is_sensitive_update and listing["status"] == "active":
        update_data["status"] = "pending_approval"
        
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
    listings = result.data if result.data else []
    
    # Add viewable images to each listing for e-commerce display
    for listing in listings:
        listing["images"] = get_listing_images(listing["id"])
    
    return listings


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

