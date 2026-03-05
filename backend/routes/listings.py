from fastapi import APIRouter, HTTPException, status, Depends, Query
from models import schemas
from db.supabase_client import db
from utils.auth import get_current_customer, get_current_admin, get_optional_current_customer
from utils.helpers import get_viewable_image_url, batch_listing_images, batch_locations, batch_stores, batch_categories
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


def get_wilayats_map(listings: list) -> dict:
    places = list({l.get("place") for l in listings if l.get("place")})
    location_ids = list({l.get("location_id") for l in listings if l.get("location_id")})
    wilayats_map = {}
    if places and location_ids:
        def wilayat_query(table):
            return table.select("*").eq("type", "city").in_("name_en", places).in_("parent_id", location_ids)
        wilayats_res = db.query("locations", wilayat_query)
        if wilayats_res.data:
            for w in wilayats_res.data:
                wilayats_map[(w.get("name_en"), w.get("parent_id"))] = w
    return wilayats_map

def get_favorites_set(current_user: Optional[dict]) -> set:
    fav_set = set()
    if current_user:
        favs = db.select("favorites", filters={"user_id": current_user["id"]})
        fav_set = {f["listing_id"] for f in favs}
    return fav_set

def format_joined_listing(listing: dict, wilayats_map: dict, fav_set: set) -> dict:
    from datetime import datetime
    now_str = datetime.utcnow().isoformat()
    from utils.helpers import get_viewable_image_url
    
    # Categories
    cat = listing.get("categories")
    if isinstance(cat, dict):
        listing["category_name_en"] = cat.get("name_en")
        listing["category_name_ar"] = cat.get("name_ar")
        
    # Images
    imgs = listing.get("listing_images") or []
    sorted_imgs = sorted(imgs, key=lambda x: (not x.get("is_main", False), x.get("display_order", 0)))
    listing["images"] = [get_viewable_image_url(img.get("image_url")) for img in sorted_imgs]
    listing.pop("listing_images", None)
    
    # Promotions: Only include product_listing so badges are correct.
    # We have separate APIs for offers and chat_screen ads.
    promos = []
    is_promoted = False
    for promo in listing.get("listing_promotions") or []:
        if promo.get("status") == "active" and (promo.get("end_date") or "") >= now_str:
            plan = promo.get("pricing_plans")
            if plan and plan.get("type") == "ad" and plan.get("ad_sub_type") == "product_listing":
                is_promoted = True
                promos.append({
                    "id": promo.get("id"),
                    "name_en": plan.get("name_en"),
                    "name_ar": plan.get("name_ar"),
                    "plan_id": promo.get("plan_id"),
                    "start_date": promo.get("start_date"),
                    "end_date": promo.get("end_date")
                })
    listing["promotions"] = promos
    listing["is_promoted"] = is_promoted
    listing.pop("listing_promotions", None)
    
    # Favorites
    listing["is_favorite"] = listing.get("id") in fav_set

    # Locations
    loc = listing.get("locations")
    if isinstance(loc, dict):
        listing["location_details"] = loc
        listing["location_name_en"] = loc.get("name_en")
        listing["location_name_ar"] = loc.get("name_ar")
    listing.pop("locations", None)

    # Wilayats
    if listing.get("place") and listing.get("location_id"):
        wilayat = wilayats_map.get((listing.get("place"), listing.get("location_id")))
        if wilayat:
            listing["place_name_en"] = wilayat.get("name_en")
            listing["place_name_ar"] = wilayat.get("name_ar")
            listing["wilayat_id"] = wilayat.get("id")
            listing["wilayat_name_en"] = wilayat.get("name_en")
            listing["wilayat_name_ar"] = wilayat.get("name_ar")

    # Store / Seller
    seller_phone = None
    store = listing.get("stores")
    listing["seller_type"] = "individual"
    if isinstance(store, dict):
        listing["seller_type"] = "store"
        listing["store_name"] = store.get("name_en") or store.get("name")
        listing["store_logo"] = store.get("logo")
        listing["store_id"] = store.get("id")
        seller_phone = store.get("store_number")
        if not listing.get("location_name_en") and store.get("locations"):
            s_loc = store.get("locations")
            if isinstance(s_loc, dict):
                listing["location_name_en"] = s_loc.get("name_en")
                listing["location_name_ar"] = s_loc.get("name_ar")
    listing.pop("stores", None)
    
    user = listing.get("app_users")
    if isinstance(user, dict):
        listing["user_name"] = user.get("name")
        listing["user_profile_picture"] = user.get("profile_picture")
        if not seller_phone:
            seller_phone = user.get("phone_number")
    listing.pop("app_users", None)

    listing["seller_phone_number"] = seller_phone

    return listing


# -------------------------------------------------
# PUBLIC / CUSTOMER ENDPOINTS
# -------------------------------------------------

@router.post("/", response_model=schemas.ListingOut, status_code=status.HTTP_201_CREATED)
def create_listing(
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
        listing["store_id"] = store_id
    
    listing["user_name"] = current_user.get("name")
    listing["user_profile_picture"] = current_user.get("profile_picture")
    listing["is_favorite"] = False

    # Inject location names for response
    if location_id:
        loc = db.select_one("locations", location_id)
        if loc:
            listing["location_name_en"] = loc.get("name_en")
            listing["location_name_ar"] = loc.get("name_ar")
    
    if payload.place_id:
        city = db.select_one("locations", payload.place_id)
        if city:
            listing["place_name_en"] = city.get("name_en")
            listing["place_name_ar"] = city.get("name_ar")
    
    # 7. Handle Images — batch insert in one query
    if payload.images:
        image_records = [
            {"listing_id": listing_id, "image_url": url, "is_main": (i == 0), "display_order": i}
            for i, url in enumerate(payload.images)
        ]
        db.insert_many("listing_images", image_records)
            
    return listing


@router.get("/", response_model=List[schemas.ListingOut])
def list_listings(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    category_id: Optional[str] = None,
    store_id: Optional[str] = None,
    user_id: Optional[str] = None,
    location_id: Optional[str] = None,
    search: Optional[str] = None,
    min_price: Optional[float] = Query(None, description="Minimum price"),
    max_price: Optional[float] = Query(None, description="Maximum price"),
    seller_type: Optional[str] = Query(None, description="Filter by seller type: 'individual' or 'store'"),
    condition: Optional[str] = Query(None, description="Filter by condition: 'new' or 'used'"),
    current_user: Optional[dict] = Depends(get_optional_current_customer)
):
    """
    List active listings with filters.
    """
    def query_func(table):
        from datetime import datetime
        now_str = datetime.utcnow().isoformat()
        
        # Only fetch active listings that are not expired
        # (expires_at is null for legacy listings that haven't been migrated yet)
        query = table.select("*, listing_images(*), stores(*, locations(*)), app_users(*), categories(*), locations(*), listing_promotions(*, pricing_plans(*))").eq("status", "active")
        query = query.or_(f"expires_at.gte.{now_str},expires_at.is.null")
        
        if category_id:
            query = query.eq("category_id", category_id)
        if store_id:
            query = query.eq("store_id", store_id)
        if location_id:
            query = query.eq("location_id", location_id)
        if condition:
            query = query.eq("condition", condition)
        if min_price is not None:
            query = query.gte("price", min_price)
        if max_price is not None:
            query = query.lte("price", max_price)
        if user_id:
            query = query.eq("user_id", user_id)
        if seller_type:
            if seller_type.lower() == "store":
                query = query.not_.is_("store_id", "null")
            elif seller_type.lower() == "individual":
                query = query.is_("store_id", "null")
        if search:
            # Supabase/PostgREST text search (simple ilike for title)
            query = query.ilike("title", f"%{search}%")
            
        return query.range(skip, skip + limit - 1).order("created_at", desc=True)

    result = db.query("listings", query_func)
    listings = result.data if result.data else []
    
    if listings:
        wilayats_map = get_wilayats_map(listings)
        fav_set = get_favorites_set(current_user)
        for i in range(len(listings)):
            listings[i] = format_joined_listing(listings[i], wilayats_map, fav_set)

    return listings

@router.get("/my-listings", response_model=List[schemas.ListingOut])
def get_my_listings(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status, e.g., 'active', 'draft', 'pending_approval'"),
    current_user: dict = Depends(get_current_customer)
):
    """
    Get all listings for the currently authenticated user.
    Returns listings regardless of status, unless status query param is provided.
    """
    user_id = current_user["id"]
    
    def query_func(table):
        query = table.select("*, listing_images(*), stores(*, locations(*)), app_users(*), categories(*), locations(*), listing_promotions(*, pricing_plans(*))").eq("user_id", user_id)
        if status:
            query = query.eq("status", status)
            
        return query.range(skip, skip + limit - 1).order("created_at", desc=True)

    result = db.query("listings", query_func)
    listings = result.data if result.data else []
    
    if listings:
        wilayats_map = get_wilayats_map(listings)
        fav_set = get_favorites_set(current_user)
        for i in range(len(listings)):
            listings[i] = format_joined_listing(listings[i], wilayats_map, fav_set)

    return listings


@router.get("/user/{user_id}", response_model=List[schemas.ListingOut])
def get_user_listings(
    user_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: Optional[dict] = Depends(get_optional_current_customer)
):
    """
    Get all active listings for a specific individual user (public view).
    """
    def query_func(table):
        from datetime import datetime
        now_str = datetime.utcnow().isoformat()
        
        query = table.select("*, listing_images(*), stores(*, locations(*)), app_users(*), categories(*), locations(*), listing_promotions(*, pricing_plans(*))").eq("user_id", user_id).eq("status", "active")
        query = query.or_(f"expires_at.gte.{now_str},expires_at.is.null")
        return query.range(skip, skip + limit - 1).order("created_at", desc=True)

    result = db.query("listings", query_func)
    listings = result.data if result.data else []
    
    if listings:
        wilayats_map = get_wilayats_map(listings)
        fav_set = get_favorites_set(current_user)
        for i in range(len(listings)):
            listings[i] = format_joined_listing(listings[i], wilayats_map, fav_set)

    return listings


@router.get("/{listing_id}", response_model=schemas.ListingOut)
def get_listing(listing_id: str, current_user: Optional[dict] = Depends(get_optional_current_customer)):
    listing = db.select_one("listings", listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    # Defaults
    listing["seller_type"] = "individual"
    listing["is_favorite"] = False
    listing["promotions"] = []
    listing["is_promoted"] = False
    
    # 1. Fetch images
    images_map = batch_listing_images([listing_id])
    listing["images"] = images_map.get(listing_id, [])
    
    # 2. Category details removed to match ListingOut
    
    # 3. Fetch Location details
    if listing.get("location_id"):
        loc = db.select_one("locations", listing["location_id"])
        if loc:
             listing["location_name_en"] = loc.get("name_en")
             listing["location_name_ar"] = loc.get("name_ar")
             
    # 4. Fetch Store / Seller details
    seller_phone = None
    if listing.get("store_id"):
        store = db.select_one("stores", listing["store_id"])
        if store:
            listing["seller_type"] = "store"
            listing["store_name"] = store.get("name_en") or store.get("name")
            listing["store_logo"] = store.get("logo")
            listing["store_id"] = store["id"]
            seller_phone = store.get("store_number")
            
    if listing.get("user_id"):
        user = db.select_one("app_users", listing["user_id"])
        if user:
            listing["user_name"] = user.get("name")
            listing["user_profile_picture"] = user.get("profile_picture")
            if not seller_phone:
                seller_phone = user.get("phone_number")
            
    listing["seller_phone_number"] = seller_phone
    
    # 5. Favorite status
    if current_user:
        fav = db.select("favorites", filters={"user_id": current_user["id"], "listing_id": listing_id})
        listing["is_favorite"] = bool(fav)
    
    # 6. Fetch active promotions
    from utils.helpers import batch_listing_promotions
    listing["promotions"] = batch_listing_promotions([listing_id]).get(listing_id, [])
    listing["is_promoted"] = len(listing["promotions"]) > 0
    
    # 7. Security: Block Unauthorized Access to Drafts/Rejected/Expired
    is_admin = False
    if current_user and current_user.get("role") == "admin":
        is_admin = True
    
    is_owner = current_user and current_user.get("id") == listing.get("user_id")
    
    if listing["status"] != "active" and not is_owner and not is_admin:
        raise HTTPException(status_code=403, detail="You do not have permission to view this listing")
    
    # Block access to expired listings for non-owners/non-admins
    if listing["status"] == "active" and listing.get("expires_at") and not is_owner and not is_admin:
        from datetime import datetime as _dt
        try:
            exp = _dt.fromisoformat(listing["expires_at"].replace("Z", "+00:00")).replace(tzinfo=None)
            if _dt.utcnow() > exp:
                raise HTTPException(status_code=410, detail="This listing has expired")
        except (ValueError, TypeError):
            pass  # If parsing fails, allow access
        
    return listing



@router.put("/{listing_id}", response_model=schemas.ListingOut)
def update_listing(
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
        
    # Fix: Resolve place_id to place name and remove place_id from update
    if "place_id" in update_data:
        city_id = update_data.pop("place_id")
        if city_id:
            city = db.select_one("locations", city_id)
            if not city or city.get("type") != "city":
                raise HTTPException(status_code=400, detail="Invalid place_id (must be a City/Wilayat)")
            update_data["place"] = city.get("name_en")
            
            # optionally update location_id to match city's parent if needed, but not strictly required
            # as frontend usually sends both.
            
    # Fix: Handle Images
    new_images = None
    if "images" in update_data:
        new_images = update_data.pop("images")
        
    updated = db.update("listings", listing_id, update_data)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update listing")
        
    # Apply Image Changes
    if new_images is not None:
        # Delete old images
        def delete_images(table):
            return table.delete().eq("listing_id", listing_id)
        db.query("listing_images", delete_images)
        
        # Insert new images
        if new_images:
            image_records = [
                {"listing_id": listing_id, "image_url": url, "is_main": (i == 0), "display_order": i}
                for i, url in enumerate(new_images)
            ]
            db.insert_many("listing_images", image_records)
            
    return updated


# -------------------------------------------------
# REPORT ENDPOINTS
# -------------------------------------------------

@router.post("/{listing_id}/report", status_code=201)
def report_listing(
    listing_id: str,
    reason: str = Query(..., min_length=5, max_length=1000),
    current_user: dict = Depends(get_current_customer),
):
    """
    Report a listing for abuse, fraud, or prohibited content.
    Each user can only report the same listing once.
    """
    user_id = current_user["id"]

    listing = db.select_one("listings", listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Block self-report
    if listing.get("user_id") == user_id:
        raise HTTPException(status_code=400, detail="You cannot report your own listing")

    # Check for duplicate report
    existing = db.select("user_reports", filters={"reported_by": user_id, "listing_id": listing_id})
    if existing:
        raise HTTPException(status_code=409, detail="You have already reported this listing")

    db.insert("user_reports", {
        "reported_by": user_id,
        "target_type": "listing",
        "listing_id": listing_id,
        "reason": reason,
    })

    logger.warning(f"Listing reported: listing={listing_id}, by={user_id}, reason={reason}")
    return {"success": True, "message": "Report submitted. Our team will review it."}


# -------------------------------------------------
# ADMIN ENDPOINTS
# -------------------------------------------------

@admin_router.get("/", response_model=List[schemas.ListingOut])
def list_all_listings_admin(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    category_id: Optional[str] = Query(None, description="Filter by category ID"),
    user_id: Optional[str] = Query(None, description="Filter by owner user ID"),
    q: Optional[str] = Query(None, description="Search by title (partial match)"),
):
    """
    Admin: List all listings with optional filters.
    Supports: status, category_id, user_id, and title search (q).
    """
    def query_func(table):
        query = table.select("*, listing_images(*), stores(*, locations(*)), app_users(*), categories(*), locations(*), listing_promotions(*, pricing_plans(*))")

        if status:
            query = query.eq("status", status)
        if category_id:
            query = query.eq("category_id", category_id)
        if user_id:
            query = query.eq("user_id", user_id)
        if q:
            # Supabase PostgREST ilike for case-insensitive partial match
            query = query.ilike("title", f"%{q}%")

        return query.range(skip, skip + limit - 1).order("created_at", desc=True)

    result = db.query("listings", query_func)
    listings = result.data if result.data else []

    if listings:
        wilayats_map = get_wilayats_map(listings)
        fav_set = get_favorites_set(None)
        for i in range(len(listings)):
            listings[i] = format_joined_listing(listings[i], wilayats_map, fav_set)

    return listings


@admin_router.put("/{listing_id}/approve")
def approve_listing(listing_id: str):
    listing = db.select_one("listings", listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found or update failed")

    from datetime import datetime as _dt, timedelta as _td
    now = _dt.utcnow()

    # ── Recalculate expires_at from NOW (approval time) ──
    # The user's purchased duration should start when the listing goes live,
    # not when they paid. Look up the original plan to get duration_days.
    new_expires_at = None
    # Find the payment that purchased this listing to get the plan duration
    payments = db.select("payments", filters={"user_id": listing["user_id"], "status": "success"})
    if payments:
        for p in sorted(payments, key=lambda x: x.get("created_at", ""), reverse=True):
            meta = p.get("metadata", {})
            if isinstance(meta, str):
                import json
                try:
                    meta = json.loads(meta)
                except:
                    meta = {}
            if meta.get("listing_id") == listing_id:
                plan_id = meta.get("listing_plan_id")
                if plan_id:
                    plan = db.select_one("pricing_plans", plan_id)
                    if plan:
                        days = plan.get("duration_days", 30)
                        new_expires_at = (now + _td(days=days)).isoformat()
                break

    listing_update = {"status": "active"}
    if new_expires_at:
        listing_update["expires_at"] = new_expires_at

    updated = db.update("listings", listing_id, listing_update)
    if not updated:
        raise HTTPException(status_code=404, detail="Listing not found or update failed")

    # ── Recalculate promotion dates from NOW (approval time) ──
    # Promotions created at payment time should start fresh at approval
    now_iso = now.isoformat()

    def pending_promo_query(table):
        return (
            table.select("id, plan_id")
            .eq("listing_id", listing_id)
            .eq("status", "pending")
        )

    pending_result = db.query("listing_promotions", pending_promo_query)
    if pending_result.data:
        for promo in pending_result.data:
            promo_plan = db.select_one("pricing_plans", promo["plan_id"]) if promo.get("plan_id") else None
            promo_days = promo_plan.get("duration_days", 7) if promo_plan else 7
            promo_end = (now + _td(days=promo_days)).isoformat()
            db.update("listing_promotions", promo["id"], {
                "status": "active",
                "start_date": now_iso,
                "end_date": promo_end,
            })
        logger.info(f"Activated {len(pending_result.data)} pending promotion(s) for approved listing {listing_id}")

    # Re-activate any boosts that were paused during a previous rejection
    def paused_promo_query(table):
        return (
            table.select("id")
            .eq("listing_id", listing_id)
            .eq("status", "paused")
            .gte("end_date", now_iso)
        )

    paused_result = db.query("listing_promotions", paused_promo_query)
    if paused_result.data:
        for promo in paused_result.data:
            db.update("listing_promotions", promo["id"], {"status": "active"})
        logger.info(f"Resumed {len(paused_result.data)} paused boost(s) for approved listing {listing_id}")

    # ── Activate pending ad_banners with fresh expiration dates ──
    pending_banners = db.select("ad_banners", filters={"listing_id": listing_id, "status": "pending_approval"})
    if pending_banners:
        for banner in pending_banners:
            banner_plan = db.select_one("pricing_plans", banner["plan_id"]) if banner.get("plan_id") else None
            banner_days = banner_plan.get("duration_days", 7) if banner_plan else 7
            banner_expires = (now + _td(days=banner_days)).isoformat()
            db.update("ad_banners", banner["id"], {
                "status": "active",
                "expires_at": banner_expires,
            })
        logger.info(f"Activated {len(pending_banners)} pending banner(s) for approved listing {listing_id}")

    # ── Push Notification: Listing approved → notify owner ──
    try:
        from services.notifications import notify_listing_approved
        if listing:
            notify_listing_approved(
                user_id=listing["user_id"],
                listing_id=listing_id,
                listing_title=listing.get("title", "Your listing"),
            )
    except Exception as notif_err:
        logger.warning(f"Listing approved notification failed (non-blocking): {notif_err}")

    return updated

@admin_router.put("/{listing_id}/reject")
def reject_listing(listing_id: str, reason: str = Query(..., min_length=1)):
    listing = db.select_one("listings", listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    updated = db.update("listings", listing_id, {"status": "rejected", "rejection_reason": reason})
    if not updated:
        raise HTTPException(status_code=500, detail="Update failed")

    # Return the quota slot to the user's active subscription (if not unlimited)
    user_id = listing.get("user_id")
    if user_id:
        from datetime import datetime
        now_iso = datetime.utcnow().isoformat()

        def sub_query(table):
            return (
                table.select("id, remaining_quota")
                .eq("user_id", user_id)
                .eq("status", "active")
                .gte("end_date", now_iso)
                .order("end_date", desc=True)
                .limit(1)
            )

        sub_result = db.query("user_subscriptions", sub_query)
        if sub_result.data:
            active_sub = sub_result.data[0]
            remaining = active_sub.get("remaining_quota", 0)
            # -1 means unlimited — don't touch it
            if remaining >= 0:
                db.update(
                    "user_subscriptions",
                    active_sub["id"],
                    {"remaining_quota": remaining + 1},
                )
                logger.info(
                    f"Quota refunded for user {user_id} after listing {listing_id} rejection. "
                    f"New remaining={remaining + 1}"
                )

    # Pause any active ad boosts so the owner doesn't lose paid boost days
    from datetime import datetime as _dt
    now_iso = _dt.utcnow().isoformat()

    def promo_query(table):
        return (
            table.select("id")
            .eq("listing_id", listing_id)
            .eq("status", "active")
            .gte("end_date", now_iso)
        )

    promo_result = db.query("listing_promotions", promo_query)
    if promo_result.data:
        for promo in promo_result.data:
            db.update("listing_promotions", promo["id"], {"status": "paused"})
        logger.info(f"Paused {len(promo_result.data)} active boost(s) for rejected listing {listing_id}")

    return updated

