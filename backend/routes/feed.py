"""
Location-aware feed endpoints.
Provides the main listing feed with promoted listings and expanding radius logic.
"""
from fastapi import APIRouter, Query, HTTPException, Depends
from typing import Optional, List
from db.supabase_client import db
from utils.auth import get_optional_current_customer
from utils.geo import resolve_location, resolve_location_by_name, get_wilayat_names_in_governorate, get_wilayats_for_governorates
from utils.helpers import batch_listing_images, batch_locations, get_viewable_image_url, batch_stores, format_joined_listing, get_wilayats_map, get_favorites_set
from utils.logger import get_logger
import math
import random
from datetime import datetime, timezone

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/feed",
    tags=["feed"]
)

PROMOTED_SLOTS_PER_PAGE = 3
MIN_RESULTS_THRESHOLD = 5  # Expand radius if fewer than this


def _get_promoted_listing_ids(
    wilayat_name: Optional[str] = None,
    governorate_id: Optional[str] = None,
    category_id: Optional[str] = None,
    exclude_ids: Optional[List[str]] = None
) -> List[str]:
    """
    Fetch listing IDs that have active, non-expired ad_banners
    of type 'product_listing' or 'top_offers'.
    Filtered by location and optionally by category.
    """
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()

    def query_func(table):
        query = (
            table.select("listing_id")
            .eq("status", "active")
            .not_.is_("listing_id", "null")
            .in_("type", ["product_listing", "top_offers"])
            .or_(f"expires_at.is.null,expires_at.gt.{now_iso}")
        )

        # Location filter: match by wilayat or governorate or global (null)
        if wilayat_name and governorate_id:
            query = query.or_(
                f"wilayat.eq.{wilayat_name},"
                f"governorate_id.eq.{governorate_id},"
                "governorate_id.is.null"
            )
        elif governorate_id:
            query = query.or_(
                f"governorate_id.eq.{governorate_id},"
                "governorate_id.is.null"
            )

        return query

    result = db.query("ad_banners", query_func)
    banners = result.data if result.data else []

    listing_ids = list({b["listing_id"] for b in banners if b.get("listing_id")})

    if exclude_ids:
        listing_ids = [lid for lid in listing_ids if lid not in set(exclude_ids)]

    return listing_ids


def _fetch_listings_by_ids(listing_ids: List[str]) -> List[dict]:
    """Fetch full listing data for a list of IDs."""
    if not listing_ids:
        return []
    listings = db.select_in("listings", "id", listing_ids)
    # Only return active listings
    return [l for l in listings if l.get("status") == "active"]


def _fetch_organic_listings(
    place_names: Optional[List[str]] = None,
    location_ids: Optional[List[str]] = None,
    category_id: Optional[str] = None,
    category_ids: Optional[List[str]] = None,
    condition: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    seller_type: Optional[str] = None,
    exclude_ids: Optional[List[str]] = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple:
    """
    Fetch organic (non-promoted) listings with location filters.
    Returns (listings, total_count).
    """
    exclude_set = set(exclude_ids) if exclude_ids else set()
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).isoformat()

    # Count query
    def count_func(table):
        # Only active listings that are not expired
        query = (
            table.select("id", count="exact")
            .eq("status", "active")
            .or_(f"expires_at.is.null,expires_at.gt.{now_iso}")
        )
        if place_names:
            query = query.in_("place", place_names)
        elif location_ids:
            query = query.in_("location_id", location_ids)
        if category_id:
            query = query.eq("category_id", category_id)
        if category_ids:
            query = query.in_("category_id", category_ids)
        if condition:
            query = query.eq("condition", condition)
        if min_price is not None:
            query = query.gte("price", min_price)
        if max_price is not None:
            query = query.lte("price", max_price)
        if seller_type:
            if seller_type.lower() == "store":
                query = query.not_.is_("store_id", "null")
            elif seller_type.lower() == "individual":
                query = query.is_("store_id", "null")
        return query.limit(0)

    count_result = db.query("listings", count_func)
    total = count_result.count if count_result.count is not None else 0

    # Data query — fetch more than needed to account for exclusions
    fetch_limit = limit + len(exclude_set) + 10

    def query_func(table):
        # Join app_users to filter locked accounts at the DB level
        query = (
            table.select(
                "*, listing_images(*), "
                "stores(*, locations(*)), "
                "app_users!inner(id, name, profile_picture, phone_number, is_active), "
                "categories(*), locations(*), listing_promotions(*, pricing_plans(*))"
            )
            .eq("status", "active")
            .eq("app_users.is_active", True)  # exclude locked-user listings
            .or_(f"expires_at.is.null,expires_at.gt.{now_iso}")
        )
        if place_names:
            query = query.in_("place", place_names)
        elif location_ids:
            query = query.in_("location_id", location_ids)
        if category_id:
            query = query.eq("category_id", category_id)
        if category_ids:
            query = query.in_("category_id", category_ids)
        if condition:
            query = query.eq("condition", condition)
        if min_price is not None:
            query = query.gte("price", min_price)
        if max_price is not None:
            query = query.lte("price", max_price)
        if seller_type:
            if seller_type.lower() == "store":
                query = query.not_.is_("store_id", "null")
            elif seller_type.lower() == "individual":
                query = query.is_("store_id", "null")
        return query.range(skip, skip + fetch_limit - 1).order("created_at", desc=True)

    result = db.query("listings", query_func)
    listings = result.data if result.data else []

    # Safety: drop any listings from locked users (belt-and-suspenders over the DB filter)
    listings = [
        l for l in listings
        if l.get("app_users") is None or l.get("app_users", {}).get("is_active", True)
    ]

    # Exclude promoted listings from organic results
    if exclude_set:
        listings = [l for l in listings if l["id"] not in exclude_set]

    # Trim to requested limit
    listings = listings[:limit]

    return listings, total


@router.get("/")
def get_feed(
    governorate: Optional[str] = Query(None, description="Governorate name (en or ar)"),
    wilayat: Optional[str] = Query(None, description="Wilayat name (en or ar)"),
    page: int = Query(0, ge=0, description="Page number (0-based)"),
    skip: int = Query(0, ge=0, description="Alternative to page (offset)"),
    limit: int = Query(20, ge=1, le=50, description="Items per page"),
    category_id: Optional[str] = Query(None, description="Filter by category"),
    condition: Optional[str] = Query(None, description="Filter: 'new' or 'used'"),
    min_price: Optional[float] = Query(None, description="Minimum price"),
    max_price: Optional[float] = Query(None, description="Maximum price"),
    seller_type: Optional[str] = Query(None, description="Filter by seller type: 'individual' or 'store'"),
    current_user: Optional[dict] = Depends(get_optional_current_customer)
):
    """
    Main location-aware listing feed with promoted listings.
    Frontend passes governorate and/or wilayat name(s) — no GPS required.

    Algorithm:
    1. Resolve governorate/wilayat name → location DB record
    2. Fetch promoted listings for that location (3 slots)
    3. Fetch organic listings for that wilayat
    4. If insufficient → expand to governorate → all Oman
    5. Mix: promoted at top + organic below
    """
    # 1. Resolve location by name
    loc = resolve_location_by_name(governorate_name=governorate, wilayat_name=wilayat)
    wilayat_name = loc["wilayat_name"]
    gov_id = loc["gov_id"]
    gov_name_en = loc["gov_name_en"]
    gov_name_ar = loc["gov_name_ar"]

    expansion_level = "wilayat"
    
    # Use skip if provided, else use page
    actual_skip = skip if skip > 0 else page * (limit - PROMOTED_SLOTS_PER_PAGE)
    organic_limit = limit - PROMOTED_SLOTS_PER_PAGE if actual_skip == 0 else limit

    # 2. Fetch promoted listings (only on first page or rotating)
    promoted_listings = []
    promoted_ids = []

    if page == 0:
        promoted_ids = _get_promoted_listing_ids(
            wilayat_name=wilayat_name,
            governorate_id=gov_id,
            category_id=category_id,
        )

        if promoted_ids:
            if category_id:
                all_promoted = _fetch_listings_by_ids(promoted_ids)
                promoted_ids = [p["id"] for p in all_promoted if p.get("category_id") == category_id]
                
            # Random rotation for fair exposure
            random.shuffle(promoted_ids)
            selected_ids = promoted_ids[:PROMOTED_SLOTS_PER_PAGE]
            
            if category_id:
                promoted_listings = [p for p in all_promoted if p["id"] in selected_ids]
            else:
                promoted_listings = _fetch_listings_by_ids(selected_ids)

            # Track impressions for served banners
            for pid in [l["id"] for l in promoted_listings]:
                try:
                    def increment_func(table):
                        return (
                            table.update({"impressions": "impressions + 1"})
                            .eq("listing_id", pid)
                            .eq("status", "active")
                        )
                    # Use raw RPC or simple approach — increment impressions
                    # Note: Supabase doesn't support atomic increment via REST easily,
                    # so we'll do a read-then-write (acceptable for impression tracking)
                except Exception:
                    pass  # Non-critical, don't fail the feed

            for listing in promoted_listings:
                listing["is_promoted"] = True

            promoted_ids = [l["id"] for l in promoted_listings]

    # 3. Fetch organic listings with expanding radius
    organic_listings = []
    total_organic = 0

    # Level 1: Wilayat
    if wilayat_name:
        organic_listings, total_organic = _fetch_organic_listings(
            place_names=[wilayat_name],
            category_id=category_id,
            condition=condition,
            min_price=min_price,
            max_price=max_price,
            seller_type=seller_type,
            exclude_ids=promoted_ids,
            skip=actual_skip,
            limit=organic_limit,
        )

    # Level 2: Expand to full governorate
    if len(organic_listings) < MIN_RESULTS_THRESHOLD and gov_id:
        expansion_level = "governorate"
        wilayat_names = get_wilayat_names_in_governorate(gov_id)
        if wilayat_names:
            organic_listings, total_organic = _fetch_organic_listings(
                place_names=wilayat_names,
                category_id=category_id,
                condition=condition,
                exclude_ids=promoted_ids,
                skip=actual_skip,
                limit=organic_limit,
            )

    # Level 3: All Oman (no location filter) — no nearby expansion in name mode
    if len(organic_listings) < MIN_RESULTS_THRESHOLD:
        expansion_level = "all"
        organic_listings, total_organic = _fetch_organic_listings(
            category_id=category_id,
            condition=condition,
            min_price=min_price,
            max_price=max_price,
            seller_type=seller_type,
            exclude_ids=promoted_ids,
            skip=actual_skip,
            limit=organic_limit,
        )

    # Mark organic listings
    for listing in organic_listings:
        listing["is_promoted"] = False

    # 4. Combine: promoted first, then organic
    all_listings = promoted_listings + organic_listings

    # 5. Enrich with images and location details
    if all_listings:
        listing_ids = [l["id"] for l in all_listings]
        images_map = batch_listing_images(listing_ids)

        location_ids = list({l["location_id"] for l in all_listings if l.get("location_id")})
        locations_map = batch_locations(location_ids)
        
        store_ids = list({l["store_id"] for l in all_listings if l.get("store_id")})
        stores_map = batch_stores(store_ids)
        
        user_ids = list({l["user_id"] for l in all_listings if l.get("user_id")})
        users_res = db.select_in("app_users", "id", user_ids) if user_ids else []
        users_map = {u["id"]: u for u in users_res}
        
        fav_set = set()
        if current_user:
            favs = db.select("favorites", filters={"user_id": current_user["id"]})
            fav_set = {f["listing_id"] for f in favs}

        # Batch fetch Wilayat details (cities)
        places = list({l["place"] for l in all_listings if l.get("place")})
        wilayats_map = {}
        if places and location_ids:
            def wilayat_query(table):
                return table.select("*").eq("type", "city").in_("name_en", places).in_("parent_id", location_ids)
            wilayats_res = db.query("locations", wilayat_query)
            if wilayats_res.data:
                for w in wilayats_res.data:
                    wilayats_map[(w["name_en"], w["parent_id"])] = w

        for listing in all_listings:
            listing["images"] = images_map.get(listing["id"], [])
            listing["is_favorite"] = listing["id"] in fav_set
            
            if listing.get("location_id"):
                loc = locations_map.get(listing["location_id"])
                if loc:
                    listing["location_details"] = loc
                    listing["location_name_en"] = loc.get("name_en")
                    listing["location_name_ar"] = loc.get("name_ar")
            
            # Inject Wilayat details
            if listing.get("place") and listing.get("location_id"):
                wilayat = wilayats_map.get((listing["place"], listing["location_id"]))
                if wilayat:
                    listing["place_name_en"] = wilayat.get("name_en")
                    listing["place_name_ar"] = wilayat.get("name_ar")
                    listing["wilayat_id"] = wilayat.get("id")
                    listing["wilayat_name_en"] = wilayat.get("name_en")
                    listing["wilayat_name_ar"] = wilayat.get("name_ar")
                    
            seller_phone = None
            if listing.get("store_id"):
                store = stores_map.get(listing["store_id"])
                if store:
                    listing["seller_type"] = "store"
                    listing["store_name"] = store.get("name_en") or store.get("name")
                    listing["store_logo"] = store.get("logo")
                    listing["store_id"] = store["id"]
                    seller_phone = store.get("store_number")
            else:
                listing["seller_type"] = "individual"
            
            if listing.get("user_id"):
                user = users_map.get(listing["user_id"])
                if user:
                    listing["user_name"] = user.get("name")
                    listing["user_profile_picture"] = user.get("profile_picture")
                    if not seller_phone:
                        seller_phone = user.get("phone_number")
                    
            listing["seller_phone_number"] = seller_phone

    # 6. Pagination math
    total = total_organic + (len(promoted_listings) if page == 0 else 0)
    pages = math.ceil(total / limit) if total > 0 else 0

    return {
        "listings": all_listings,
        "resolved_location": {
            "wilayat_en": wilayat_name,
            "governorate_en": gov_name_en,
            "governorate_ar": gov_name_ar,
            "expansion_level": expansion_level,
        },
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }


@router.get("/offers")
def get_location_offers(
    governorate: Optional[str] = Query(None, description="Governorate name (en or ar)"),
    wilayat: Optional[str] = Query(None, description="Wilayat name (en or ar)"),
    page: int = Query(0, ge=0),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
):
    """
    Location-based offers feed.
    Returns active offer-type banners and user boosted top-offers.
    Offers with no location (admin-created global) are always included.
    """
    loc = resolve_location_by_name(governorate_name=governorate, wilayat_name=wilayat)
    wilayat_name = loc["wilayat_name"]
    gov_id = loc["gov_id"]

    # Use skip if provided, else use page
    actual_skip = skip if skip > 0 else page * limit

    now_iso = datetime.now(timezone.utc).isoformat()

    def query_func(table):
        query = (
            table.select("*, listings(*, categories(*), locations(*))")
            .eq("status", "active")
            .in_("type", ["offers", "top_offers"])
            .or_(f"expires_at.is.null,expires_at.gt.{now_iso}")
        )

        # Location: match wilayat, governorate, or global (no location set) for top_offers
        # 'offers' (admin offers) are always included regardless of location
        if wilayat_name and gov_id:
            query = query.or_(
                f"type.eq.offers,"
                f"and(type.eq.top_offers,or(wilayat.eq.{wilayat_name},governorate_id.eq.{gov_id},governorate_id.is.null))"
            )
        elif gov_id:
            query = query.or_(
                f"type.eq.offers,"
                f"and(type.eq.top_offers,or(governorate_id.eq.{gov_id},governorate_id.is.null))"
            )
        else:
            # No location provided, only show admin offers
            query = query.eq("type", "offers")

        return query.range(actual_skip, actual_skip + limit - 1).order("created_at", desc=True)

    # Count
    def count_func(table):
        query = (
            table.select("id", count="exact")
            .eq("status", "active")
            .in_("type", ["offers", "top_offers"])
            .or_(f"expires_at.is.null,expires_at.gt.{now_iso}")
        )
        if wilayat_name and gov_id:
            query = query.or_(
                f"type.eq.offers,"
                f"and(type.eq.top_offers,or(wilayat.eq.{wilayat_name},governorate_id.eq.{gov_id},governorate_id.is.null))"
            )
        elif gov_id:
            query = query.or_(
                f"type.eq.offers,"
                f"and(type.eq.top_offers,or(governorate_id.eq.{gov_id},governorate_id.is.null))"
            )
        else:
            # No location provided, only show admin offers
            query = query.eq("type", "offers")
            
        return query.limit(0)

    count_result = db.query("ad_banners", count_func)
    total = count_result.count if count_result.count is not None else 0

    result = db.query("ad_banners", query_func)
    banners = result.data if result.data else []

    # 1. Gather IDs for batch fetching
    listing_ids = list({b["listing_id"] for b in banners if b.get("listing_id")})
    
    # Batch fetch listing images
    images_map = batch_listing_images(listing_ids)
    
    # 2. Batch fetch listing owners (stores/users) to get mobile numbers
    listing_owners_map = {}
    if listing_ids:
        def l_query(table):
            return table.select("id, store_id, user_id").in_("id", listing_ids)
        listing_owners_res = db.query("listings", l_query)
        if listing_owners_res.data:
            listing_owners_map = {l["id"]: l for l in listing_owners_res.data}

    store_ids = list({l["store_id"] for l in listing_owners_map.values() if l.get("store_id")})
    user_ids = list({l["user_id"] for l in listing_owners_map.values() if l.get("user_id")})
    # Also include banner users if any
    b_user_ids = list({b["user_id"] for b in banners if b.get("user_id")})
    user_ids = list(set(user_ids + b_user_ids))

    stores_map = batch_stores(store_ids)
    users_res = db.select_in("app_users", "id", user_ids) if user_ids else []
    users_map = {u["id"]: u for u in users_res}

    # 3. Process each offer
    offers = []
    for b in banners:
        is_admin_offer = b.get("type") == "offers"
        listing_id = b.get("listing_id")
        
        # Unified Images key
        list_of_images = []
        if listing_id:
            # Listing-based images
            list_of_images = images_map.get(listing_id, [])
        else:
            # Admin-based images (from ad_banners table)
            b_imgs = b.get("images")
            if b_imgs:
                list_of_images = b_imgs if isinstance(b_imgs, list) else [b_imgs]
            elif b.get("image_url"):
                list_of_images = [b["image_url"]]

        # Determine Mobile/WhatsApp Number and Store Details
        # Admin offers can have a specific whatsapp_number
        mobile_number = b.get("whatsapp_number")
        store_name = None
        store_logo = None
        store_id = None
        
        # Fallback to listing owner if it's a boosted listing
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
        
        # Final fallback for admin offers if no whatsapp_number set explicitly
        if not mobile_number and is_admin_offer and b.get("user_id"):
            u = users_map.get(b["user_id"])
            if u:
                mobile_number = u.get("phone_number")

        offers.append({
            "id": b["id"],
            "listing_id": listing_id,
            "name": b.get("name"),
            "image_url": b.get("image_url") or (list_of_images[0] if list_of_images else None),
            "images": list_of_images, # Unified key for multiple images
            "link_url": b.get("link_url") if is_admin_offer else None,
            "whatsapp_number": mobile_number if is_admin_offer else None,
            "store_mobile_number": mobile_number if not is_admin_offer else None,
            "store_name": store_name,
            "store_logo": store_logo,
            "store_id": store_id,
            "is_admin_offer": is_admin_offer,
            "description": b.get("description"),
            "created_at": b.get("created_at")
        })

    pages = math.ceil(total / limit) if total > 0 else 0

    return {
        "offers": offers,
        "resolved_location": {
            "wilayat_en": wilayat_name,
            "governorate_en": loc["gov_name_en"],
        },
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }



@router.get("/nearby-stores")
def get_nearby_stores(
    governorate: Optional[str] = Query(None, description="Governorate name (en or ar)"),
    wilayat: Optional[str] = Query(None, description="Wilayat name (en or ar)"),
    page: int = Query(0, ge=0),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    min_rating: Optional[float] = Query(None, description="Minimum average rating")
):
    """
    Location-aware store listing. Shows stores in user's wilayat/governorate.
    Frontend passes governorate/wilayat names — no GPS required.
    """
    loc = resolve_location_by_name(governorate_name=governorate, wilayat_name=wilayat)
    wilayat_name = loc["wilayat_name"]
    gov_id = loc["gov_id"]
    expansion_level = "wilayat"

    # Use skip if provided, else use page
    actual_skip = skip if skip > 0 else page * limit

    def _count_stores(gov_filter=None, wilayat_filter=None, all_mode=False):
        def count_func(table):
            query = table.select("id", count="exact").eq("status", "active")
            if wilayat_filter:
                query = query.eq("wilayat", wilayat_filter)
            elif gov_filter:
                if isinstance(gov_filter, list):
                    query = query.in_("governorate_id", gov_filter)
                else:
                    query = query.eq("governorate_id", gov_filter)
            return query.limit(0)
        
        if min_rating is not None:
            return 0  # We will count after fetching and filtering
            
        result = db.query("stores", count_func)
        return result.count if result.count is not None else 0

    def _fetch_stores(gov_filter=None, wilayat_filter=None, all_mode=False):
        def query_func(table):
            query = table.select("id, name, name_ar, status, logo").eq("status", "active")
            if wilayat_filter:
                query = query.eq("wilayat", wilayat_filter)
            elif gov_filter:
                if isinstance(gov_filter, list):
                    query = query.in_("governorate_id", gov_filter)
                else:
                    query = query.eq("governorate_id", gov_filter)
                    
            if min_rating is None:
                query = query.range(actual_skip, actual_skip + limit - 1)
                
            return query.order("created_at", desc=True)
        result = db.query("stores", query_func)
        return result.data if result.data else []

    # Level 1: Wilayat
    stores = []
    total = 0
    if wilayat_name:
        total = _count_stores(wilayat_filter=wilayat_name)
        stores = _fetch_stores(wilayat_filter=wilayat_name)

    # Level 2: Governorate
    if len(stores) < MIN_RESULTS_THRESHOLD and gov_id:
        expansion_level = "governorate"
        total = _count_stores(gov_filter=gov_id)
        stores = _fetch_stores(gov_filter=gov_id)

    # Level 3: All Oman (expansion_level "nearby" is for GPS mode)
    if len(stores) < MIN_RESULTS_THRESHOLD:
        expansion_level = "all"
        total = _count_stores(all_mode=True)
        stores = _fetch_stores(all_mode=True)

    # Batch fetch ratings
    if stores:
        store_ids = [s["id"] for s in stores]
        all_reviews = db.select_in("store_reviews", "store_id", store_ids, columns="store_id,rating")
        ratings_map = {}
        for r in all_reviews:
            ratings_map.setdefault(r["store_id"], []).append(r["rating"])
        for store in stores:
            ratings = ratings_map.get(store["id"], [])
            store["average_rating"] = round(sum(ratings) / len(ratings), 1) if ratings else 0.0
            store["total_reviews"] = len(ratings)

    if min_rating is not None:
        stores = [s for s in stores if s.get("average_rating", 0.0) >= min_rating]
        total = len(stores)
        stores = stores[actual_skip : actual_skip + limit]

    pages = math.ceil(total / limit) if total > 0 else 0

    return {
        "stores": stores,
        "resolved_location": {
            "wilayat_en": wilayat_name,
            "governorate_en": loc["gov_name_en"],
            "expansion_level": expansion_level,
        },
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }


@router.get("/resolve-location")
def resolve_user_location(
    lat: float = Query(..., description="User's latitude"),
    lng: float = Query(..., description="User's longitude"),
):
    """
    Utility endpoint to resolve coordinates to a wilayat/governorate.
    Frontend can use this to display the user's detected location name.
    """
    location = resolve_location(lat, lng)
    wilayat = location.get("wilayat")
    governorate = location.get("governorate")

    return {
        "wilayat": {
            "id": wilayat["id"] if wilayat else None,
            "name_en": wilayat["name_en"] if wilayat else None,
            "name_ar": wilayat["name_ar"] if wilayat else None,
            "distance_km": wilayat.get("distance_km") if wilayat else None,
        },
        "governorate": {
            "id": governorate["id"] if governorate else None,
            "name_en": governorate["name_en"] if governorate else None,
            "name_ar": governorate["name_ar"] if governorate else None,
        },
    }


@router.get("/category/{category_id}")
def get_category_feed(
    category_id: str,
    governorate: Optional[str] = Query(None, description="Governorate name (en or ar)"),
    wilayat: Optional[str] = Query(None, description="Wilayat name (en or ar)"),
    page: int = Query(0, ge=0),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    condition: Optional[str] = Query(None, description="Filter: 'new' or 'used'"),
    min_price: Optional[float] = Query(None, description="Minimum price"),
    max_price: Optional[float] = Query(None, description="Maximum price"),
    seller_type: Optional[str] = Query(None, description="Filter by seller type: 'individual' or 'store'"),
    current_user: Optional[dict] = Depends(get_optional_current_customer)
):
    """
    Location-aware feed for a specific category.
    Returns category info, subcategories, and the product listings.
    """
    # 1. Fetch category details
    category = db.select_one("categories", category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
        
    if category.get("image_url"):
        category["image_url"] = get_viewable_image_url(category["image_url"])

    # 2. Fetch list of direct subcategories vs descendants
    all_active = db.select("categories", filters={"is_active": True, "is_deleted": False})
    
    # Direct children for the UI icons/list
    subcategories = [c for c in all_active if c.get("parent_id") == category_id]
    for subcat in subcategories:
        if subcat.get("image_url"):
            subcat["image_url"] = get_viewable_image_url(subcat["image_url"])

    # All descendants for the listing search (recursive)
    def get_descendants(parent_id, categories):
        desc = []
        for c in categories:
            if c.get("parent_id") == parent_id:
                desc.append(c["id"])
                desc.extend(get_descendants(c["id"], categories))
        return desc
    
    target_category_ids = [category_id] + get_descendants(category_id, all_active)

    # 3. Resolve location by name (if provided)
    resolved_wilayat_name = None
    gov_id = None
    expansion_level = "all"

    resolved_location_data = {
        "wilayat_en": None,
        "wilayat_ar": None,
        "governorate_en": None,
        "governorate_ar": None,
        "expansion_level": "all",
    }

    if governorate or wilayat:
        loc = resolve_location_by_name(governorate_name=governorate, wilayat_name=wilayat)
        resolved_wilayat_name = loc["wilayat_name"]
        gov_id = loc["gov_id"]
        expansion_level = "wilayat" if resolved_wilayat_name else ("governorate" if gov_id else "all")
        resolved_location_data = {
            "wilayat_en": resolved_wilayat_name,
            "wilayat_ar": None,
            "governorate_en": loc["gov_name_en"],
            "governorate_ar": loc["gov_name_ar"],
            "expansion_level": expansion_level,
        }

    # 4. Fetch listings with location-aware expansion
    actual_skip = skip if skip > 0 else page * limit
    
    organic_listings = []
    total_organic = 0
    
    # NEW: Handle promoted listings in category feed
    promoted_listings = []
    promoted_ids = []
    
    if actual_skip == 0:
        # Fetch all possible promoted banners for this location
        p_ids = _get_promoted_listing_ids(
            wilayat_name=resolved_wilayat_name,
            governorate_id=gov_id,
        )
        
        if p_ids:
            # Filter by matching category hierarchy in memory
            # (Fetching up to 100 promoted items to check hierarchy is fast)
            all_promoted = _fetch_listings_by_ids(p_ids)
            
            # Match hierarchy: listing category must be the target or its child
            target_ids_set = set(target_category_ids)
            promoted_ids = [p["id"] for p in all_promoted if p.get("category_id") in target_ids_set]
            
            # Shuffle and choose top 3
            random.shuffle(promoted_ids)
            selected_ids = promoted_ids[:PROMOTED_SLOTS_PER_PAGE]
            
            promoted_listings = [p for p in all_promoted if p["id"] in selected_ids]
            
            for listing in promoted_listings:
                listing["is_promoted"] = True
            
            # Prepare organic limits to account for promoted slots
            organic_limit = limit - len(promoted_listings)
            # actual_skip is already 0
        else:
            organic_limit = limit
    else:
        # For offsets > 0, we fetch full organic limit
        # Calculation should be consistent with the regular feed
        # We assume 3 slots were taken on page 0
        organic_limit = limit
        if skip == 0: # originated from 'page'
            actual_skip = page * (limit - PROMOTED_SLOTS_PER_PAGE) if page > 0 else 0
        
    promoted_ids_to_exclude = [l["id"] for l in promoted_listings]

    # Level 1: Wilayat
    if resolved_wilayat_name:
        organic_listings, total_organic = _fetch_organic_listings(
            place_names=[resolved_wilayat_name],
            category_ids=target_category_ids,
            condition=condition,
            min_price=min_price,
            max_price=max_price,
            seller_type=seller_type,
            exclude_ids=promoted_ids_to_exclude,
            skip=actual_skip,
            limit=organic_limit,
        )

    # Level 2: Expand to governorate
    if len(organic_listings) < MIN_RESULTS_THRESHOLD and gov_id:
        expansion_level = "governorate"
        resolved_location_data["expansion_level"] = expansion_level
        wilayat_names = get_wilayat_names_in_governorate(gov_id)
        if wilayat_names:
            organic_listings, total_organic = _fetch_organic_listings(
                place_names=wilayat_names,
                category_ids=target_category_ids,
                condition=condition,
                min_price=min_price,
                max_price=max_price,
                seller_type=seller_type,
                exclude_ids=promoted_ids_to_exclude,
                skip=actual_skip,
                limit=organic_limit,
            )

    # Level 3: Expand to nearby governorates — not applicable in name-based mode
    # (no proximity ranking without GPS; fall straight to All Oman)

    # Level 4: All Oman
    if len(organic_listings) < MIN_RESULTS_THRESHOLD:
        expansion_level = "all"
        resolved_location_data["expansion_level"] = expansion_level
        organic_listings, total_organic = _fetch_organic_listings(
            category_ids=target_category_ids,
            condition=condition,
            min_price=min_price,
            max_price=max_price,
            seller_type=seller_type,
            exclude_ids=promoted_ids_to_exclude,
            skip=actual_skip,
            limit=organic_limit,
        )

    for listing in organic_listings:
        listing["is_promoted"] = False

    # 5. Combine and enrich
    all_listings = promoted_listings + organic_listings
    
    if all_listings:
        listing_ids = [l["id"] for l in all_listings]
        images_map = batch_listing_images(listing_ids)

        loc_ids = list({l["location_id"] for l in all_listings if l.get("location_id")})
        locations_map = batch_locations(loc_ids)
        
        store_ids = list({l["store_id"] for l in all_listings if l.get("store_id")})
        stores_map = batch_stores(store_ids)
        
        user_ids = list({l["user_id"] for l in all_listings if l.get("user_id")})
        users_res = db.select_in("app_users", "id", user_ids) if user_ids else []
        users_map = {u["id"]: u for u in users_res}
        
        fav_set = set()
        if current_user:
            favs = db.select("favorites", filters={"user_id": current_user["id"]})
            fav_set = {f["listing_id"] for f in favs}

        # Batch fetch Wilayat details (cities)
        places = list({l["place"] for l in all_listings if l.get("place")})
        wilayats_map = {}
        if places and loc_ids:
            def wilayat_query(table):
                return table.select("*").eq("type", "city").in_("name_en", places).in_("parent_id", loc_ids)
            wilayats_res = db.query("locations", wilayat_query)
            if wilayats_res.data:
                for w in wilayats_res.data:
                    wilayats_map[(w["name_en"], w["parent_id"])] = w

        for l in all_listings:
            l["images"] = images_map.get(l["id"], [])
            l["is_favorite"] = l["id"] in fav_set
            if l.get("location_id"):
                loc = locations_map.get(l["location_id"])
                if loc:
                    l["location_details"] = loc
                    l["location_name_en"] = loc.get("name_en")
                    l["location_name_ar"] = loc.get("name_ar")
            
            # Inject Wilayat details
            if l.get("place") and l.get("location_id"):
                wilayat = wilayats_map.get((l["place"], l["location_id"]))
                if wilayat:
                    l["place_name_en"] = wilayat.get("name_en")
                    l["place_name_ar"] = wilayat.get("name_ar")
                    l["wilayat_id"] = wilayat.get("id")
                    l["wilayat_name_en"] = wilayat.get("name_en")
                    l["wilayat_name_ar"] = wilayat.get("name_ar")
                    
            seller_phone = None
            if l.get("store_id"):
                store = stores_map.get(l.get("store_id"))
                if store:
                    l["seller_type"] = "store"
                    l["store_name"] = store.get("name_en") or store.get("name")
                    l["store_logo"] = store.get("logo")
                    l["store_id"] = store["id"]
                    seller_phone = store.get("store_number")
            else:
                l["seller_type"] = "individual"
            
            if l.get("user_id"):
                user = users_map.get(l.get("user_id"))
                if user:
                    l["user_name"] = user.get("name")
                    l["user_profile_picture"] = user.get("profile_picture")
                    if not seller_phone:
                        seller_phone = user.get("phone_number")
                    
            l["seller_phone_number"] = seller_phone
    total = total_organic + (len(promoted_listings) if page == 0 else 0)
    pages = math.ceil(total / limit) if total > 0 else 0

    return {
        "category": category,
        "subcategories": subcategories,
        "listings": all_listings,
        "resolved_location": resolved_location_data,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }


@router.get("/chat-screen-ad")
def get_chat_screen_ad(
    governorate: Optional[str] = Query(None, description="Governorate name (en or ar)"),
    wilayat: Optional[str] = Query(None, description="Wilayat name (en or ar)"),
    exclude_ids: Optional[str] = Query(None, description="Comma-separated listing IDs to exclude (recently shown)"),
):
    """
    Chat screen ad — returns a SINGLE sponsored listing for display in the chat screen.

    Production rotation logic:
    1. Fetch all active chat_screen promotions (non-expired)
    2. Filter by user's location (expanding: wilayat → governorate → all)
    3. Exclude recently shown IDs (sent by frontend)
    4. Pick one using weighted random (fewer impressions = higher chance)
    5. Increment impression counter for fair distribution
    6. If all excluded, reset and pick from full pool (cycling)

    Frontend should:
    - Call this endpoint each time a chat screen opens
    - Pass the last 3-5 shown listing IDs in exclude_ids
    - Display the single returned ad
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Fetch all active chat_screen promotions (non-expired)
    def promo_query(table):
        return (
            table.select("id, listing_id, plan_id, start_date, end_date, impressions")
            .eq("status", "active")
            .gte("end_date", now_iso)
        )

    promo_result = db.query("listing_promotions", promo_query)
    all_promos = promo_result.data if promo_result.data else []

    if not all_promos:
        return {"ad": None, "has_ads": False}

    # 2. Filter to chat_screen plans only
    plan_ids = list({p["plan_id"] for p in all_promos if p.get("plan_id")})
    plans_res = db.select_in("pricing_plans", "id", plan_ids) if plan_ids else []
    chat_screen_plan_ids = {
        p["id"] for p in plans_res
        if p.get("type") == "ad" and p.get("ad_sub_type") == "chat_screen"
    }

    chat_promos = [p for p in all_promos if p.get("plan_id") in chat_screen_plan_ids]

    if not chat_promos:
        return {"ad": None, "has_ads": False}

    listing_ids = list({p["listing_id"] for p in chat_promos if p.get("listing_id")})

    # 3. Fetch the listings (only active, non-expired)
    def listing_query(table):
        return (
            table.select(
                "id, title, price, currency, condition, place, location_id, "
                "store_id, user_id, category_id, status, expires_at"
            )
            .in_("id", listing_ids)
            .eq("status", "active")
            .or_(f"expires_at.is.null,expires_at.gt.{now_iso}")
        )

    listing_result = db.query("listings", listing_query)
    active_listings = listing_result.data if listing_result.data else []

    if not active_listings:
        return {"ad": None, "has_ads": False}

    active_listing_ids = {l["id"] for l in active_listings}
    active_listings_map = {l["id"]: l for l in active_listings}

    # Keep only promos whose listing is still active
    eligible_promos = [p for p in chat_promos if p.get("listing_id") in active_listing_ids]

    if not eligible_promos:
        return {"ad": None, "has_ads": False}

    # 4. Location filtering with expanding radius
    expansion_level = "all"
    resolved_wilayat = None
    resolved_gov = None

    if governorate or wilayat:
        loc = resolve_location_by_name(governorate_name=governorate, wilayat_name=wilayat)
        resolved_wilayat = loc["wilayat_name"]
        resolved_gov = loc["gov_name_en"]
        gov_id = loc["gov_id"]

        if resolved_wilayat:
            # Level 1: Wilayat match
            wilayat_promos = [
                p for p in eligible_promos
                if active_listings_map.get(p["listing_id"], {}).get("place") == resolved_wilayat
            ]
            if wilayat_promos:
                expansion_level = "wilayat"
                eligible_promos = wilayat_promos
            elif gov_id:
                # Level 2: Governorate match
                gov_wilayats = get_wilayat_names_in_governorate(gov_id) or []
                gov_promos = [
                    p for p in eligible_promos
                    if active_listings_map.get(p["listing_id"], {}).get("place") in gov_wilayats
                ]
                if gov_promos:
                    expansion_level = "governorate"
                    eligible_promos = gov_promos
                # else: Level 3 — keep all (expansion_level stays "all")
        elif gov_id:
            gov_wilayats = get_wilayat_names_in_governorate(gov_id) or []
            gov_promos = [
                p for p in eligible_promos
                if active_listings_map.get(p["listing_id"], {}).get("place") in gov_wilayats
            ]
            if gov_promos:
                expansion_level = "governorate"
                eligible_promos = gov_promos

    # 5. Exclude recently shown IDs (cycling: if all excluded, reset)
    excluded = set()
    if exclude_ids:
        excluded = {eid.strip() for eid in exclude_ids.split(",") if eid.strip()}

    non_excluded = [p for p in eligible_promos if p["listing_id"] not in excluded]

    # If everything was excluded, cycle back to full pool
    if not non_excluded:
        non_excluded = eligible_promos

    # 6. Weighted random selection (lower impressions = higher weight)
    # Formula: weight = 1 / (impressions + 1)  → new ads (0 impressions) get weight 1.0
    weights = []
    for p in non_excluded:
        imp = p.get("impressions") or 0
        weights.append(1.0 / (imp + 1))

    # Pick one using weighted random (stdlib — no numpy needed)
    selected_promo = random.choices(non_excluded, weights=weights, k=1)[0]
    selected_listing_id = selected_promo["listing_id"]

    # 7. Increment impressions (fire-and-forget, non-blocking)
    try:
        current_imp = selected_promo.get("impressions") or 0
        db.update("listing_promotions", selected_promo["id"], {
            "impressions": current_imp + 1
        })
    except Exception:
        pass  # Non-critical, don't fail the request

    # 8. Enrich the selected listing
    listing = active_listings_map[selected_listing_id]

    # Images
    images_map = batch_listing_images([selected_listing_id])
    listing["images"] = images_map.get(selected_listing_id, [])

    # Category
    if listing.get("category_id"):
        cat = db.select_one("categories", listing["category_id"])
        if cat:
            listing["category_name_en"] = cat.get("name_en")
            listing["category_name_ar"] = cat.get("name_ar")

    # Location
    if listing.get("location_id"):
        loc_data = db.select_one("locations", listing["location_id"])
        if loc_data:
            listing["location_name_en"] = loc_data.get("name_en")
            listing["location_name_ar"] = loc_data.get("name_ar")

    # Wilayat
    if listing.get("place") and listing.get("location_id"):
        def wil_q(table):
            return (
                table.select("name_en, name_ar")
                .eq("type", "city")
                .eq("name_en", listing["place"])
                .eq("parent_id", listing["location_id"])
                .limit(1)
            )
        wil_res = db.query("locations", wil_q)
        if wil_res.data:
            listing["wilayat_name_en"] = wil_res.data[0].get("name_en")
            listing["wilayat_name_ar"] = wil_res.data[0].get("name_ar")

    # Store / Seller
    seller_phone = None
    listing["seller_type"] = "individual"

    if listing.get("store_id"):
        store = db.select_one("stores", listing["store_id"])
        if store:
            listing["seller_type"] = "store"
            listing["store_name"] = store.get("name_en") or store.get("name")
            listing["store_logo"] = store.get("logo")
            seller_phone = store.get("store_number")

    if listing.get("user_id"):
        user = db.select_one("app_users", listing["user_id"])
        if user:
            listing["user_name"] = user.get("name")
            listing["user_profile_picture"] = user.get("profile_picture")
            if not seller_phone:
                seller_phone = user.get("phone_number")

    listing["seller_phone_number"] = seller_phone

    # Promotion info
    plans_map = {p["id"]: p for p in plans_res}
    plan = plans_map.get(selected_promo.get("plan_id"), {})
    listing["chat_screen_promotion"] = {
        "promotion_id": selected_promo["id"],
        "plan_name_en": plan.get("name_en"),
        "plan_name_ar": plan.get("name_ar"),
        "start_date": selected_promo.get("start_date"),
        "end_date": selected_promo.get("end_date"),
    }

    return {
        "ad": listing,
        "has_ads": True,
        "total_pool_size": len(eligible_promos),
        "expansion_level": expansion_level,
        "resolved_location": {
            "wilayat_en": resolved_wilayat,
            "governorate_en": resolved_gov,
        },
    }
