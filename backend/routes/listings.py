from fastapi import APIRouter, HTTPException, status, Depends, Query
from models import schemas
from db.supabase_client import db
from utils.auth import get_current_customer, get_current_admin
from utils.helpers import get_viewable_image_url, batch_listing_images, batch_locations, batch_stores
from utils.logger import get_logger
from typing import List, Optional
from datetime import datetime

logger = get_logger(__name__)

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

def enrich_attributes_with_type(attributes_values: dict, category_id: str) -> dict:
    """
    Enriches attributes values with their type and labels from category schema.
    """
    if not attributes_values:
        return {}
    category = db.select_one("categories", category_id)
    if not category or not category.get("attributes_schema"):
        return attributes_values
        
    schema_map = {attr.get("name"): attr for attr in category.get("attributes_schema", [])}
    enriched_attrs = {}
    
    for key, val in attributes_values.items():
        # Handle case where value is already enriched (e.g., during update sent back by frontend)
        actual_val = val.get("value") if isinstance(val, dict) and "value" in val else val
        
        attr_def = schema_map.get(key, {})
        enriched_attrs[key] = {
            "value": actual_val,
            "type": attr_def.get("type", "text_field"),
            "label_en": attr_def.get("label_en", key),
            "label_ar": attr_def.get("label_ar", "")
        }
    return enriched_attrs

# -------------------------------------------------
# PUBLIC / CUSTOMER ENDPOINTS
# -------------------------------------------------

@router.post("/", response_model=schemas.ListingOut, status_code=status.HTTP_201_CREATED)
async def create_listing(
    payload: schemas.ListingCreate,
    current_user: dict = Depends(get_current_customer)
):
    """
    Create a new listing (draft).
    
    Business Rules:
    - All listings require a paid subscription plan (no free listings)
    - Listing is created as 'draft' — user must go to /payments/checkout with a plan
    - After payment, status moves to 'pending_approval' for admin review
    - Category must be a leaf node
    - Store is optional (auto-assigned if user owns a store)
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
    
    # 3. Verify Governorate (Location)
    location_id = payload.location_id
    if location_id:
        location = db.select_one("locations", location_id)
        if not location:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid location_id (Governorate)"
            )
        if location.get("type") != "state":
             raise HTTPException(status_code=400, detail="location_id must be a Governorate (State)")

    # Verify Place (City)
    place_name = None
    if payload.place_id:
        city = db.select_one("locations", payload.place_id)
        if not city:
             raise HTTPException(status_code=400, detail="Invalid place_id (City)")
        if city.get("type") != "city":
             raise HTTPException(status_code=400, detail="place_id must be a City (Wilayat)")
        
        # Check parent
        if city.get("parent_id") != location_id:
             raise HTTPException(status_code=400, detail="City does not belong to the selected Governorate")
             
        place_name = city.get("name_en")

    # 4. Verify Condition
    if payload.condition not in ['new', 'used']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Condition must be 'new' or 'used'"
        )

    # 4. REMOVED Quota Check - Now handled at Checkout
    # Listing is created as 'draft' first. Quota is checked when user hits "Checkout".
    # if not is_store_user:
    #     ... (Logic moved to /payments/checkout)
    
    # 5. Prepare Data
    data = payload.dict(exclude={"images", "place_id"})
    
    # Map place name from city object
    if place_name:
        data["place"] = place_name
    
    data["user_id"] = user_id
    data["location_id"] = location_id
    data["status"] = "draft" # Default to draft
    
    # Force store_id if store user
    if is_store_user:
        data["store_id"] = store_id
    else:
        data["store_id"] = None
        
    # Enrich attributes with type and labels based on category schema
    if data.get("attributes_values"):
        data["attributes_values"] = enrich_attributes_with_type(
            data["attributes_values"], payload.category_id
        )
    
    # 5. Create Listing
    listing = db.insert("listings", data)
    if not listing:
        raise HTTPException(status_code=500, detail="Failed to create listing")
        
    listing_id = listing["id"]
    
    # 6. Inject store / seller info for response
    listing["seller_type"] = "store" if is_store_user else "individual"
    if is_store_user:
        listing["store_name"] = user_stores[0].get("name_en") or user_stores[0].get("name")
        listing["store_logo"] = user_stores[0].get("logo")
    
    # 7. Handle Images — batch insert in one query
    if payload.images:
        image_records = [
            {"listing_id": listing_id, "image_url": url, "is_main": (i == 0), "display_order": i}
            for i, url in enumerate(payload.images)
        ]
        db.insert_many("listing_images", image_records)
            
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
        from datetime import datetime
        now_str = datetime.utcnow().isoformat()
        
        # Only fetch active listings that are not expired
        # (expires_at is null for legacy listings that haven't been migrated yet)
        query = table.select("*").eq("status", "active")
        query = query.or_(f"expires_at.gte.{now_str},expires_at.is.null")
        
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
    
    if listings:
        # Batch fetch images — 1 query instead of N
        listing_ids = [l["id"] for l in listings]
        images_map = batch_listing_images(listing_ids)

        # Batch fetch locations — 1 query instead of N
        location_ids = list({l["location_id"] for l in listings if l.get("location_id")})
        locations_map = batch_locations(location_ids)

        # Batch fetch stores
        store_ids = list({l["store_id"] for l in listings if l.get("store_id")})
        stores_map = batch_stores(store_ids)
        
        # Batch fetch active promotions
        promos_res = db.select_in("listing_promotions", "listing_id", listing_ids)
        promotions_map = {}
        if promos_res:
            now_str = datetime.utcnow().isoformat()
            for promo in promos_res:
                if promo.get("status") == "active" and promo.get("end_date", "") >= now_str:
                    pid = promo["listing_id"]
                    if pid not in promotions_map:
                        promotions_map[pid] = []
                    promotions_map[pid].append(promo)
                    
        # Batch fetch users for phone numbers
        user_ids = list({l["user_id"] for l in listings if l.get("user_id")})
        users_res = db.select_in("app_users", "id", user_ids) if user_ids else []
        users_map = {u["id"]: u for u in users_res}

        for listing in listings:
            listing["images"] = images_map.get(listing["id"], [])
            listing["promotions"] = promotions_map.get(listing["id"], [])
            
            if listing.get("location_id"):
                loc = locations_map.get(listing["location_id"])
                if loc:
                    listing["location_details"] = loc
            
            seller_phone = None
            if listing.get("store_id"):
                store = stores_map.get(listing["store_id"])
                if store:
                    listing["seller_type"] = "store"
                    listing["store_name"] = store.get("name_en") or store.get("name")
                    listing["store_logo"] = store.get("logo")
                    seller_phone = store.get("store_number")
            
            if not seller_phone and listing.get("user_id"):
                user = users_map.get(listing["user_id"])
                if user:
                    seller_phone = user.get("phone_number")
                    
            listing["seller_phone_number"] = seller_phone

    return listings


@router.get("/{listing_id}", response_model=schemas.ListingOut)
async def get_listing(listing_id: str):
    listing = db.select_one("listings", listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    # Fetch images
    images_map = batch_listing_images([listing_id])
    listing["images"] = images_map.get(listing_id, [])
    
    if listing.get("location_id"):
        loc = db.select_one("locations", listing["location_id"])
        if loc:
             listing["location_details"] = loc
             
    seller_phone = None
    if listing.get("store_id"):
        store = db.select_one("stores", listing["store_id"])
        if store:
            listing["seller_type"] = "store"
            listing["store_name"] = store.get("name_en") or store.get("name")
            listing["store_logo"] = store.get("logo")
            seller_phone = store.get("store_number")
            
    if not seller_phone and listing.get("user_id"):
        user = db.select_one("app_users", listing["user_id"])
        if user:
            seller_phone = user.get("phone_number")
            
    listing["seller_phone_number"] = seller_phone
    
    # Fetch active promotions
    now_str = datetime.utcnow().isoformat()
    promos = db.select("listing_promotions", filters={"listing_id": listing_id, "status": "active"})
    active_promos = [p for p in promos if p.get("end_date", "") >= now_str] if promos else []
    listing["promotions"] = active_promos
    
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
        
    # Enrich attributes if they are being updated
    if "attributes_values" in update_data and update_data["attributes_values"]:
        cat_id = update_data.get("category_id") or listing.get("category_id")
        update_data["attributes_values"] = enrich_attributes_with_type(
            update_data["attributes_values"], cat_id
        )
        
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
    
    # Batch fetch images — 1 query instead of N
    if listings:
        listing_ids = [l["id"] for l in listings]
        images_map = batch_listing_images(listing_ids)
        
        # Batch fetch stores
        store_ids = list({l["store_id"] for l in listings if l.get("store_id")})
        stores_map = batch_stores(store_ids)
        
        # Batch fetch users for phone numbers
        user_ids = list({l["user_id"] for l in listings if l.get("user_id")})
        users_res = db.select_in("app_users", "id", user_ids) if user_ids else []
        users_map = {u["id"]: u for u in users_res}
        
        for listing in listings:
            listing["images"] = images_map.get(listing["id"], [])
            
            seller_phone = None
            if listing.get("store_id"):
                store = stores_map.get(listing["store_id"])
                if store:
                    listing["seller_type"] = "store"
                    listing["store_name"] = store.get("name_en") or store.get("name")
                    listing["store_logo"] = store.get("logo")
                    seller_phone = store.get("store_number")
            
            if not seller_phone and listing.get("user_id"):
                user = users_map.get(listing["user_id"])
                if user:
                    seller_phone = user.get("phone_number")
                    
            listing["seller_phone_number"] = seller_phone
    
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

