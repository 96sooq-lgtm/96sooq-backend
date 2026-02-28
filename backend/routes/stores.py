from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from models import schemas
from db.supabase_client import db
from utils.auth import get_current_customer, get_current_admin, decode_customer_token
from utils.helpers import batch_listing_images, batch_user_info
from typing import List, Optional

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
async def create_store(
    payload: schemas.StoreCreate,
    current_user: dict = Depends(get_current_customer)
):
    """
    Create a new store. 
    Business Logic: First store might be free, otherwise check for plan payments (future).
    For now, sets status to 'pending_approval' or 'active' depending on policy.
    """
    user_id = current_user["id"]
    
    # Check if user already has a store? 
    # Logic: "for a user first store is free if sae user wnated to create mulitple store there will be a rpice"
    # We will just allow creation for now.
    
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
async def check_user_store(
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
async def list_stores(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    my_stores: bool = Query(False, description="If true, return only the authenticated user's stores (requires Bearer token)"),
    status: Optional[str] = Query(None, description="Filter by status — only applies when my_stores=true"),
    location_id: Optional[str] = Query(None, description="Filter by governorate or wilayat UUID. If null, returns all stores."),
):
    """
    List stores.
    - No auth / my_stores=false → public active stores (paginated)
    - my_stores=true + Bearer token → caller's own stores (all statuses, optional status filter)
    - location_id → filter by governorate (UUID) or wilayat (resolved to name)
    """
    user_id = None

    if my_stores:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Bearer token required for my_stores")
        token = auth_header.split(" ", 1)[1]
        try:
            current_user = decode_customer_token(token)
            user_id = current_user["id"]
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
        query = table.select("id, name, name_ar, logo")
        if user_id:
            query = query.eq("user_id", user_id)
            if status:
                query = query.eq("status", status)
        else:
            query = query.eq("status", "active")

        if governorate_filter:
            query = query.eq("governorate_id", governorate_filter)
        if wilayat_filter:
            query = query.eq("wilayat", wilayat_filter)

        return query.range(skip, skip + limit - 1).order("created_at", desc=True)

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

    return stores


@router.get("/{store_id}", response_model=schemas.StoreOut)
async def get_store(store_id: str, request: Request):
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
async def update_store(
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
        
    updated = db.update("stores", store_id, update_data)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update store")
        
    return updated


# -------------------------------------------------
# STORE REVIEWS
# -------------------------------------------------

@router.post("/{store_id}/reviews", response_model=schemas.StoreReviewOut, status_code=status.HTTP_201_CREATED)
async def create_store_review(
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
async def get_store_reviews(
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
async def get_store_listings(
    store_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Get all active listings for a store.
    Used for the Posts tab in store detail page.
    """
    # Verify store exists
    store = db.select_one("stores", store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    def query_func(table):
        return (
            table.select("*")
            .eq("store_id", store_id)
            .eq("status", "active")
            .range(skip, skip + limit - 1)
            .order("created_at", desc=True)
        )

    result = db.query("listings", query_func)
    listings = result.data if result.data else []

    # Batch fetch images — 1 query instead of N
    if listings:
        listing_ids = [l["id"] for l in listings]
        images_map = batch_listing_images(listing_ids)
        for listing in listings:
            listing["images"] = images_map.get(listing["id"], [])

    return listings


# -------------------------------------------------
# ADMIN ENDPOINTS
# -------------------------------------------------

@admin_router.get("/", response_model=schemas.AdminStoreListResponse)
async def list_all_stores_admin(
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
async def get_store_detail_admin(store_id: str):
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
async def approve_store(store_id: str):
    updated = db.update("stores", store_id, {"status": "active"})
    if not updated:
         raise HTTPException(status_code=404, detail="Store not found or update failed")
    return updated

@admin_router.put("/{store_id}/reject")
async def reject_store(store_id: str):
    updated = db.update("stores", store_id, {"status": "rejected"})
    if not updated:
         raise HTTPException(status_code=404, detail="Store not found or update failed")
    return updated

@admin_router.put("/{store_id}/lock")
async def lock_store(store_id: str):
    """
    Admin: Deactivate a store. Status → 'inactive'.
    """ 
    updated = db.update("stores", store_id, {"status": "inactive"})
    if not updated:
        raise HTTPException(status_code=404, detail="Store not found")
    return updated

@admin_router.put("/{store_id}/unlock")
async def unlock_store(store_id: str):
    """
    Admin: Reactivate a store. Status → 'active'.   
    """
    updated = db.update("stores", store_id, {"status": "active"})
    if not updated:
        raise HTTPException(status_code=404, detail="Store not found")
    return updated
