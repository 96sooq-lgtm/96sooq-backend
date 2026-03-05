from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from models import schemas
from db.supabase_client import db
from utils.auth import get_current_admin, get_current_customer
from utils.logger import get_logger

logger = get_logger(__name__)
from datetime import datetime, timedelta

from utils.helpers import batch_listing_images, batch_stores
from db.supabase_client import db

def enrich_banners(banners):
    listing_ids = list({b["listing_id"] for b in banners if b.get("listing_id")})
    images_map = batch_listing_images(listing_ids) if listing_ids else {}

    # 1. Fetch listing owners (stores/users) to get mobile numbers and store names
    listing_owners_map = {}
    if listing_ids:
        def l_query(table):
            return table.select("id, store_id, user_id").in_("id", listing_ids)
        listing_owners_res = db.query("listings", l_query)
        if listing_owners_res.data:
            listing_owners_map = {l["id"]: l for l in listing_owners_res.data}

    # Gather store_ids and user_ids
    store_ids = list({l["store_id"] for l in listing_owners_map.values() if l.get("store_id")})
    user_ids = list({l["user_id"] for l in listing_owners_map.values() if l.get("user_id")})
    b_user_ids = list({b["user_id"] for b in banners if b.get("user_id")})
    user_ids = list(set(user_ids + b_user_ids))

    stores_map = batch_stores(store_ids)
    users_res = db.select_in("app_users", "id", user_ids) if user_ids else []
    users_map = {u["id"]: u for u in users_res}

    for b in banners:
        is_admin_offer = b.get("type") == "offers"
        b["creator_role"] = "user" if b.get("user_id") else "admin"
        b["is_admin_offer"] = is_admin_offer
        
        # Unify images key
        list_of_images = []
        if b.get("listing_id"):
            list_of_images = images_map.get(b["listing_id"], [])
        else:
            b_imgs = b.get("images")
            if b_imgs:
                list_of_images = b_imgs if isinstance(b_imgs, list) else [b_imgs]
            elif b.get("image_url"):
                list_of_images = [b["image_url"]]
        
        b["images"] = list_of_images
        
        # Always make sure image_url is set to the first image if not provided
        if not b.get("image_url") and list_of_images:
            b["image_url"] = list_of_images[0]

        # Details Extractions
        mobile_number = b.get("whatsapp_number")
        store_name = None
        store_logo = None
        store_id = None
        listing_id = b.get("listing_id")
        
        if not mobile_number and listing_id and listing_id in listing_owners_map:
            l_owner = listing_owners_map[listing_id]
            if l_owner.get("store_id"):
                store = stores_map.get(l_owner["store_id"])
                if store:
                    mobile_number = store.get("store_number")
                    store_name = store.get("name_en") or store.get("name")
                    store_logo = store.get("logo")
                    store_id = store.get("id")
            
            if not mobile_number and l_owner.get("user_id"):
                user = users_map.get(l_owner["user_id"])
                if user:
                    mobile_number = user.get("phone_number")
        
        if not mobile_number and is_admin_offer and b.get("user_id"):
            u = users_map.get(b["user_id"])
            if u:
                mobile_number = u.get("phone_number")

        b["whatsapp_number"] = mobile_number if is_admin_offer else None
        b["store_mobile_number"] = mobile_number if not is_admin_offer else None
        b["store_name"] = store_name
        b["store_logo"] = store_logo
        b["store_id"] = store_id
            
    return banners

def enrich_banner(banner):
    return enrich_banners([banner])[0]

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
def boost_listing(
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

        # User banners are always active immediately — no admin approval needed
        banner_status = "active"

        data = {
            "user_id": user_id,
            "listing_id": payload.listing_id,
            "type": payload.type,
            "name": name,
            "image_url": image_url,
            "description": payload.description,
            "status": banner_status,
            # Inherit location from listing for location-targeted promotions
            "governorate_id": listing.get("location_id"),
            "wilayat": listing.get("place"),
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

        return enrich_banner(banner)


    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{banner_id}/pay", response_model=schemas.AdBannerOut)
def pay_for_banner(
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

    return enrich_banner(updated)

@router.get("/my-banners", response_model=List[schemas.AdBannerOut])
def list_my_banners(
    current_user: dict = Depends(get_current_customer)
):
    """
    List logged-in user's banners.
    """
    banners = db.select("ad_banners", filters={"user_id": current_user["id"]})
    return enrich_banners(banners if banners else [])

@router.get("/public", response_model=List[schemas.AdBannerOut])
def list_active_banners(
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
    return enrich_banners(result.data if result.data else [])


@router.get("/home", response_model=List[schemas.AdBannerOut])
def get_home_banners(
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
    return enrich_banners(result.data if result.data else [])


@router.get("/featured", response_model=List[schemas.AdBannerOut])
def get_featured_banners():
    """
    Public — no auth required.
    Returns all active admin-created banners (no listing_id).
    Frontend displays these as a carousel/slider.
    """
    def query_func(table):
        return (
            table.select("*")
            .eq("status", "active")
            .is_("listing_id", "null")  # admin banners only
            .order("created_at", desc=True)
        )

    result = db.query("ad_banners", query_func)
    return enrich_banners(result.data if result.data else [])


@router.get("/offers", response_model=List[schemas.AdBannerOut])
def get_offers():
    """
    Public — no auth required.
    Returns all active offer-type admin banners (multiple images each).
    """
    def query_func(table):
        return (
            table.select("*")
            .eq("status", "active")
            .eq("type", "offers")
            .order("created_at", desc=True)
        )

    result = db.query("ad_banners", query_func)
    return enrich_banners(result.data if result.data else [])



# -------------------------------------------------
# ADMIN ENDPOINTS
# -------------------------------------------------

@admin_router.post("/", response_model=schemas.AdBannerOut, status_code=status.HTTP_201_CREATED)
def create_banner_admin(
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
            "images": payload.images or [],
            "link_url": payload.link_url,
            "whatsapp_number": payload.whatsapp_number,
            "description": payload.description,
            "status": "active",
            "duration_days": payload.duration_days,
            "expires_at": (datetime.utcnow() + timedelta(days=payload.duration_days)).isoformat(),
        }

        banner = db.insert("ad_banners", data)
        if not banner:
            raise HTTPException(status_code=500, detail="Failed to create banner")

        return enrich_banner(banner)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@admin_router.get("/", response_model=List[schemas.AdBannerOut])
def list_all_banners_admin(
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
    return enrich_banners(result.data if result.data else [])

@admin_router.patch("/{banner_id}", response_model=schemas.AdBannerOut)
def update_banner_admin(
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

    return enrich_banner(updated)


@admin_router.put("/{banner_id}/approve", response_model=schemas.AdBannerOut)
def approve_banner(banner_id: str):
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
        
    return enrich_banner(updated)

@admin_router.put("/{banner_id}/reject", response_model=schemas.AdBannerOut)
def reject_banner(banner_id: str):
    updated = db.update("ad_banners", banner_id, {"status": "rejected"})
    if not updated:
         raise HTTPException(status_code=404, detail="Banner not found")
    return enrich_banner(updated)

@admin_router.delete("/{banner_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_banner(banner_id: str):
    success = db.delete("ad_banners", banner_id)
    if not success:
         raise HTTPException(status_code=404, detail="Banner not found")
