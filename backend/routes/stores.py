from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from models import schemas
from db.supabase_client import db
from utils.auth import get_current_customer, get_current_admin, decode_customer_token
from utils.helpers import batch_listing_images, batch_user_info
from utils.logger import get_logger
from typing import List, Optional

logger = get_logger(__name__)

# Public/User Router
router = APIRouter(
    prefix="/api/stores",
    tags=["stores"]
)

# Admin Router (could be separate file, but grouping by feature for now)
admin_router = APIRouter(
    prefix="/api/admin/stores",
    tags=["admin-stores"],
    dependencies=[Depends(get_current_admin)]
)


# -------------------------------------------------
# PUBLIC / CUSTOMER ENDPOINTS
# -------------------------------------------------

@router.post("/", response_model=schemas.StoreOut, status_code=status.HTTP_201_CREATED)
def create_store(
    payload: schemas.StoreCreate,
    current_user: dict = Depends(get_current_customer)
):
    """
    Create a new store.
    Business rule: One store per user account.
    """
    user_id = current_user["id"]

    # Enforce one store per user
    existing_stores = db.select("stores", filters={"user_id": user_id})
    if existing_stores:
        raise HTTPException(
            status_code=400,
            detail=f"You already have a store (ID: {existing_stores[0]['id']}). Only one store per account is allowed."
        )

    # Validate Governorate
    if payload.governorate_id:
        governorate = db.select_one("locations", str(payload.governorate_id))
        if not governorate:
            raise HTTPException(status_code=400, detail="Invalid governorate_id")
        if governorate.get("type") != "state":
            raise HTTPException(status_code=400, detail="governorate_id must be a Governorate (State)")

    # Validate Wilayat
    wilayat_name = None
    if payload.wilayat_id:
        wilayat = db.select_one("locations", str(payload.wilayat_id))
        if not wilayat:
            raise HTTPException(status_code=400, detail="Invalid wilayat_id")
        if wilayat.get("type") != "city":
            raise HTTPException(status_code=400, detail="wilayat_id must be a Wilayat (City)")

        # Check wilayat belongs to the selected governorate
        if wilayat.get("parent_id") != str(payload.governorate_id):
            raise HTTPException(status_code=400, detail="Wilayat does not belong to the selected Governorate")

        wilayat_name = wilayat.get("name_en")

    # Build DB payload
    data = payload.dict()
    data["governorate_id"] = str(payload.governorate_id)
    data["wilayat_id"] = str(payload.wilayat_id)
    if data.get("plan_id"):
        data["plan_id"] = str(payload.plan_id) if payload.plan_id else None

    data["user_id"] = user_id
    data["name"] = payload.name_en

    if wilayat_name:
        data["wilayat"] = wilayat_name

    # Remove schema-only fields not stored directly
    data.pop("name_en", None)
    data.pop("wilayat_id", None)
    
    data["status"] = "active" # Auto-approve stores as per new requirement

    store = db.insert("stores", data)
    if not store:
        raise HTTPException(status_code=500, detail="Failed to create store")
        
    return store


@router.get("/check")
def check_user_store(
    current_user: dict = Depends(get_current_customer)
):
    """
    Check if the authenticated user already has a store.
    Returns { has_store: bool, store: {...} | null }
    Frontend uses this when user taps 'Add Listing':
    - has_store=true  → skip store creation, go directly to listing
    - has_store=false → show store creation step first
    """
    stores = db.select("stores", filters={"user_id": current_user["id"]})
    if stores:
        return {"has_store": True, "store": stores[0]}
    return {"has_store": False, "store": None}


@router.get("/", response_model=List[schemas.StoreListOut])
def list_stores(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    my_stores: bool = Query(False, description="If true, return only the authenticated user's stores (requires Bearer token)"),
    status: Optional[str] = Query(None, description="Filter by status — only applies when fetching own stores"),
    location_id: Optional[str] = Query(None, description="Filter by governorate or wilayat UUID. If null, returns all stores."),
    user_id: Optional[str] = Query(None, description="If 'current', return the authenticated user's stores (all statuses)."),
    min_rating: Optional[float] = Query(None, description="Minimum average rating")
):
    """
    List stores.
    - No auth / my_stores=false / user_id!=current → public active stores (paginated)
    - my_stores=true OR user_id=current (+ Bearer token) → caller's own stores (all statuses, optional status filter)
    - location_id → filter by governorate (UUID) or wilayat (resolved to name)
    """
    owner_id = None

    if my_stores or user_id == "current":
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Bearer token required to fetch own stores")
        token = auth_header.split(" ", 1)[1]
        try:
            current_user = decode_customer_token(token)
            owner_id = current_user["id"]
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Resolve location_id → determine if it's a governorate or wilayat
    governorate_filter = None
    wilayat_filter = None
    if location_id:
        location = db.select_one("locations", location_id)
        if not location:
            raise HTTPException(status_code=400, detail="Invalid location_id")
        if location.get("type") == "state":
            governorate_filter = location_id          # filter by UUID column
        elif location.get("type") in ("city", "district"):
            wilayat_filter = location.get("name_en")  # filter by text name column

    def query_func(table):
        query = table.select("id, name, name_ar, status, logo")
        if owner_id:
            query = query.eq("user_id", owner_id)
            if status:
                query = query.eq("status", status)
        else:
            query = query.eq("status", "active")

        if governorate_filter:
            query = query.eq("governorate_id", governorate_filter)
        if wilayat_filter:
            query = query.eq("wilayat", wilayat_filter)

        if min_rating is None:
            query = query.range(skip, skip + limit - 1)
            
        return query.order("created_at", desc=True)

    result = db.query("stores", query_func)
    stores = result.data if result.data else []

    # Batch fetch ratings for all stores — 1 query
    if stores:
        store_ids = [s["id"] for s in stores]
        all_reviews = db.select_in("store_reviews", "store_id", store_ids, columns="store_id,rating")

        # Group ratings by store
        ratings_map = {}
        for r in all_reviews:
            ratings_map.setdefault(r["store_id"], []).append(r["rating"])

        for store in stores:
            ratings = ratings_map.get(store["id"], [])
            store["average_rating"] = round(sum(ratings) / len(ratings), 1) if ratings else 0.0
            store["total_reviews"] = len(ratings)
            
    if min_rating is not None:
        stores = [s for s in stores if s.get("average_rating", 0.0) >= min_rating]
        stores = stores[skip : skip + limit]

    return stores


@router.get("/{store_id}", response_model=schemas.StoreOut)
def get_store(store_id: str, request: Request):
    store = db.select_one("stores", store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    # Add average rating and review count for store header
    all_reviews = db.select("store_reviews", columns="rating", filters={"store_id": store_id})
    if all_reviews:
        ratings = [r["rating"] for r in all_reviews]
        store["average_rating"] = round(sum(ratings) / len(ratings), 1)
        store["total_reviews"] = len(ratings)
    else:
        store["average_rating"] = 0.0
        store["total_reviews"] = 0

    # Check if logged-in user owns this store (optional auth)
    store["is_own_store"] = False
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            token = auth_header.split(" ", 1)[1]
            current_user = decode_customer_token(token)
            store["is_own_store"] = (store["user_id"] == current_user["id"])
        except Exception:
            pass  # Invalid token — just default to False

    # Resolve governorate and wilayat names
    if store.get("governorate_id"):
        gov = db.select_one("locations", store["governorate_id"], columns="name_en,name_ar")
        if gov:
            store["governorate_en"] = gov.get("name_en")
            store["governorate_ar"] = gov.get("name_ar")

    # Wilayat is stored as name_en text — look up the Arabic name
    if store.get("wilayat"):
        store["wilayat_en"] = store["wilayat"]
        wilayat_records = db.select("locations", columns="name_ar", filters={"name_en": store["wilayat"], "type": "city"})
        if wilayat_records:
            store["wilayat_ar"] = wilayat_records[0].get("name_ar")

    return store


@router.put("/{store_id}", response_model=schemas.StoreOut)
def update_store(
    store_id: str, 
    payload: schemas.StoreUpdate,
    current_user: dict = Depends(get_current_customer)
):
    # Verify ownership
    store = db.select_one("stores", store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
        
    if store["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to update this store")
        
    update_data = payload.dict(exclude_unset=True)
    if "status" in update_data:
        del update_data["status"]
        
    # Fix: Map wilayat_id to wilayat name
    if "wilayat_id" in update_data:
        wil_id = update_data.pop("wilayat_id")
        if wil_id:
            wilayat = db.select_one("locations", str(wil_id))
            if not wilayat or wilayat.get("type") != "city":
                raise HTTPException(status_code=400, detail="Invalid wilayat_id (must be a Wilayat/City)")
            update_data["wilayat"] = wilayat.get("name_en")
            
    # Fix: Ensure governorate_id is string if provided
    if "governorate_id" in update_data and update_data["governorate_id"]:
        update_data["governorate_id"] = str(update_data["governorate_id"])
        
    updated = db.update("stores", store_id, update_data)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update store")
        
    return updated


# -------------------------------------------------
# STORE REVIEWS
# -------------------------------------------------

@router.post("/{store_id}/reviews", response_model=schemas.StoreReviewOut, status_code=status.HTTP_201_CREATED)
def create_store_review(
    store_id: str,
    payload: schemas.StoreReviewCreate,
    current_user: dict = Depends(get_current_customer)
):
    """
    Submit a review for a store. Rating 1-5 with optional comment.
    - User cannot review their own store
    - User can only submit one review per store
    """
    user_id = current_user["id"]

    # Verify store exists
    store = db.select_one("stores", store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    # Prevent self-review
    if store["user_id"] == user_id:
        raise HTTPException(status_code=400, detail="You cannot review your own store")

    # Check for existing review
    existing = db.select("store_reviews", filters={
        "reviewer_id": user_id,
        "store_id": store_id,
    })
    if existing:
        raise HTTPException(status_code=400, detail="You have already reviewed this store")

    review = db.insert("store_reviews", {
        "reviewer_id": user_id,
        "store_id": store_id,
        "rating": payload.rating,
        "comment": payload.comment,
    })
    if not review:
        raise HTTPException(status_code=500, detail="Failed to submit review")

    # Attach reviewer name
    reviewer = db.select_one("app_users", user_id, columns="name")
    review["reviewer_name"] = reviewer.get("name") if reviewer else None

    return review


@router.get("/{store_id}/reviews", response_model=schemas.StoreReviewsResponse)
def get_store_reviews(
    store_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Get all reviews for a store with rating breakdown.
    Used for the Reviews tab in store detail page.
    """
    import math

    # Verify store exists
    store = db.select_one("stores", store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    # Get ALL reviews for rating calculation
    all_reviews = db.select("store_reviews", filters={"store_id": store_id})
    all_reviews = all_reviews or []
    total = len(all_reviews)

    # Calculate rating breakdown
    rating_breakdown = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
    for r in all_reviews:
        key = str(r.get("rating", 0))
        if key in rating_breakdown:
            rating_breakdown[key] += 1

    # Average rating
    if total > 0:
        avg = sum(r["rating"] for r in all_reviews) / total
        average_rating = round(avg, 1)
    else:
        average_rating = 0.0

    # Paginated slice from all_reviews (avoid second query)
    sorted_reviews = sorted(all_reviews, key=lambda r: r.get("created_at", ""), reverse=True)
    reviews = sorted_reviews[skip:skip + limit]

    # Batch fetch reviewer names — 1 query instead of N
    if reviews:
        reviewer_ids = list({r["reviewer_id"] for r in reviews})
        users_map = batch_user_info(reviewer_ids)
        for review in reviews:
            owner = users_map.get(review["reviewer_id"], {})
            review["reviewer_name"] = owner.get("name")

    page = (skip // limit) + 1 if limit else 1
    pages = math.ceil(total / limit) if limit and total else 0

    return {
        "reviews": reviews,
        "average_rating": average_rating,
        "total_reviews": total,
        "rating_breakdown": rating_breakdown,
        "page": page,
        "limit": limit,
        "pages": pages,
    }


@router.get("/{store_id}/listings", response_model=List[schemas.ListingOut])
def get_store_listings(
    store_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status (pending, active, sold, rejected, all)"),
    request: Request = None
):
    """
    Get listings for a store.
    - Public: only active (and sold) listings.
    - Owner: all listings regardless of status, with optional status filtering.
    """
    # Verify store exists
    store = db.select_one("stores", store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    is_owner = False
    if request:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                from utils.auth import decode_customer_token
                current_user = decode_customer_token(token)
                if current_user and current_user.get("id") == store.get("user_id"):
                    is_owner = True
            except Exception:
                pass # Not logged in or invalid token, treat as public

    def query_func(table):
        query = table.select("*").eq("store_id", store_id)
        
        if status and status.lower() != "all":
            # If a specific status is requested
            if not is_owner and status not in ["active", "sold"]:
                # Restricted: public can only search within active/sold
                query = query.eq("status", "active")
            else:
                query = query.eq("status", status)
        else:
            # No status filter provided or "all" requested
            if not is_owner:
                # Public default: active only
                query = query.eq("status", "active")
            # if is_owner and no status: returns everything for that store (all statuses)

        return (
            query
            .range(skip, skip + limit - 1)
            .order("created_at", desc=True)
        )

    result = db.query("listings", query_func)
    listings = result.data if result.data else []

    # Finalize seller info
    seller_phone = store.get("store_number")
    if not seller_phone and store.get("user_id"):
        user = db.select_one("app_users", store.get("user_id"))
        if user:
            seller_phone = user.get("phone_number")

    # Batch enrichment — 1 query per related table instead of N
    if listings:
        listing_ids = [l["id"] for l in listings]
        from utils.helpers import batch_listing_images, batch_locations, batch_categories, batch_listing_promotions
        
        images_map = batch_listing_images(listing_ids)
        promotions_map = batch_listing_promotions(listing_ids)
        
        location_ids = list({l["location_id"] for l in listings if l.get("location_id")})
        locations_map = batch_locations(location_ids)
        
        category_ids = list({l["category_id"] for l in listings if l.get("category_id")})
        categories_map = batch_categories(category_ids)
        
        parent_cat_ids = list({cat.get("parent_id") for cat in categories_map.values() if cat.get("parent_id")})
        parent_categories_map = batch_categories(parent_cat_ids) if parent_cat_ids else {}
        
        # Batch fetch Wilayat details (cities)
        places = list({l["place"] for l in listings if l.get("place")})
        wilayats_map = {}
        if places and location_ids:
            def wilayat_query(table):
                return table.select("*").eq("type", "city").in_("name_en", places).in_("parent_id", location_ids)
            wilayats_res = db.query("locations", wilayat_query)
            if wilayats_res.data:
                for w in wilayats_res.data:
                    wilayats_map[(w["name_en"], w["parent_id"])] = w

        for listing in listings:
            listing["images"] = images_map.get(listing["id"], [])
            listing["promotions"] = promotions_map.get(listing["id"], [])
            listing["seller_type"] = "store"
            listing["store_name"] = store.get("name_en") or store.get("name")
            listing["store_logo"] = store.get("logo")
            listing["store_id"] = store["id"]
            listing["seller_phone_number"] = seller_phone
            
            # Categories
            cat = categories_map.get(listing.get("category_id"))
            if cat:
                listing["category_name_en"] = cat.get("name_en")
                listing["category_name_ar"] = cat.get("name_ar")
                p_id = cat.get("parent_id")
                if p_id:
                    p_cat = parent_categories_map.get(p_id)
                    if p_cat:
                        listing["parent_category_name_en"] = p_cat.get("name_en")
                        listing["parent_category_name_ar"] = p_cat.get("name_ar")

            # Locations
            if listing.get("location_id"):
                loc = locations_map.get(listing["location_id"])
                if loc:
                    listing["location_details"] = loc
                    listing["location_name_en"] = loc.get("name_en")
                    listing["location_name_ar"] = loc.get("name_ar")
            
            # Wilayat details
            if listing.get("place") and listing.get("location_id"):
                wilayat = wilayats_map.get((listing["place"], listing["location_id"]))
                if wilayat:
                    listing["place_name_en"] = wilayat.get("name_en")
                    listing["place_name_ar"] = wilayat.get("name_ar")
                    listing["wilayat_id"] = wilayat.get("id")
                    listing["wilayat_name_en"] = wilayat.get("name_en")
                    listing["wilayat_name_ar"] = wilayat.get("name_ar")

    return listings



# -------------------------------------------------
# ADMIN ENDPOINTS
# -------------------------------------------------

@admin_router.get("/", response_model=schemas.AdminStoreListResponse)
def list_all_stores_admin(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status: active, locked"),
    search: Optional[str] = Query(None, description="Search by store name (English or Arabic)"),
):
    """
    Admin: List all stores with pagination, optional status filter, and search.
    """
    import math

    # --- Count query ---
    def count_func(table):
        query = table.select("id", count="exact")
        if status:
            query = query.eq("status", status)
        if search:
            query = query.or_(f"name.ilike.%{search}%,name_ar.ilike.%{search}%")
        return query

    count_result = db.query("stores", count_func)
    total = count_result.count if count_result.count is not None else 0

    # --- Data query (only needed columns) ---
    def query_func(table):
        query = table.select("id,name,name_ar,status,logo")
        if status:
            query = query.eq("status", status)
        if search:
            query = query.or_(f"name.ilike.%{search}%,name_ar.ilike.%{search}%")
        return query.range(skip, skip + limit - 1).order("created_at", desc=True)

    result = db.query("stores", query_func)
    stores = result.data if result.data else []

    page = (skip // limit) + 1 if limit else 1
    pages = math.ceil(total / limit) if limit and total else 0

    return {
        "stores": stores,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }


@admin_router.get("/{store_id}")
def get_store_detail_admin(store_id: str):
    """
    Admin: Get full store details including owner info, rating, and listing count.
    Total: 4 queries (store + owner + reviews + listing count).
    """
    store = db.select_one("stores", store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    # Owner info — 1 query
    owner = db.select_one("app_users", store["user_id"], columns="id,name,phone_number,email")
    store["owner_name"] = owner.get("name") if owner else None
    store["owner_phone"] = owner.get("phone_number") if owner else None
    store["owner_email"] = owner.get("email") if owner else None

    # Rating stats — 1 query (select only rating column)
    reviews = db.select("store_reviews", columns="rating", filters={"store_id": store_id})
    if reviews:
        ratings = [r["rating"] for r in reviews]
        store["average_rating"] = round(sum(ratings) / len(ratings), 1)
        store["total_reviews"] = len(ratings)
    else:
        store["average_rating"] = 0.0
        store["total_reviews"] = 0

    # Listing count — 1 query
    def count_listings(table):
        return table.select("id", count="exact").eq("store_id", store_id).limit(0)

    listings_result = db.query("listings", count_listings)
    store["total_listings"] = listings_result.count or 0

    return store


@admin_router.put("/{store_id}/approve")
def approve_store(store_id: str):
    updated = db.update("stores", store_id, {"status": "active"})
    if not updated:
         raise HTTPException(status_code=404, detail="Store not found or update failed")
    return updated

@admin_router.put("/{store_id}/reject")
def reject_store(store_id: str):
    updated = db.update("stores", store_id, {"status": "rejected"})
    if not updated:
         raise HTTPException(status_code=404, detail="Store not found or update failed")
    return updated

@admin_router.put("/{store_id}/lock")
def lock_store(store_id: str):
    """
    Admin: Deactivate a store. Status → 'inactive'.
    """ 
    updated = db.update("stores", store_id, {"status": "inactive"})
    if not updated:
        raise HTTPException(status_code=404, detail="Store not found")
    return updated

@admin_router.put("/{store_id}/unlock")
def unlock_store(store_id: str):
    """
    Admin: Reactivate a store. Status → 'active'.   
    """
    updated = db.update("stores", store_id, {"status": "active"})
    if not updated:
        raise HTTPException(status_code=404, detail="Store not found")
    return updated
