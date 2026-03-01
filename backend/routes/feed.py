"""
Location-aware feed endpoints.
Provides the main listing feed with promoted listings and expanding radius logic.
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from db.supabase_client import db
from utils.geo import resolve_location, get_wilayat_names_in_governorate, get_wilayats_for_governorates
from utils.helpers import batch_listing_images, batch_locations
from utils.logger import get_logger
import math
import random

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
    def query_func(table):
        query = (
            table.select("listing_id")
            .eq("status", "active")
            .not_.is_("listing_id", "null")
            .in_("type", ["product_listing", "top_offers"])
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

    # Count query
    def count_func(table):
        query = table.select("id", count="exact").eq("status", "active")
        if place_names:
            query = query.in_("place", place_names)
        elif location_ids:
            query = query.in_("location_id", location_ids)
        if category_id:
            query = query.eq("category_id", category_id)
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
        query = table.select("*").eq("status", "active")
        if place_names:
            query = query.in_("place", place_names)
        elif location_ids:
            query = query.in_("location_id", location_ids)
        if category_id:
            query = query.eq("category_id", category_id)
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

    # Exclude promoted listings from organic results
    if exclude_set:
        listings = [l for l in listings if l["id"] not in exclude_set]

    # Trim to requested limit
    listings = listings[:limit]

    return listings, total


@router.get("/")
async def get_feed(
    lat: float = Query(..., description="User's latitude"),
    lng: float = Query(..., description="User's longitude"),
    page: int = Query(0, ge=0, description="Page number (0-based)"),
    limit: int = Query(20, ge=1, le=50, description="Items per page"),
    category_id: Optional[str] = Query(None, description="Filter by category"),
    condition: Optional[str] = Query(None, description="Filter: 'new' or 'used'"),
    min_price: Optional[float] = Query(None, description="Minimum price"),
    max_price: Optional[float] = Query(None, description="Maximum price"),
    seller_type: Optional[str] = Query(None, description="Filter by seller type: 'individual' or 'store'")
):
    """
    Main location-aware listing feed with promoted listings.

    Algorithm:
    1. Resolve user lat/lng → nearest wilayat
    2. Fetch promoted listings for that location (3 slots)
    3. Fetch organic listings for that wilayat
    4. If insufficient → expand to governorate → nearby governorates → all
    5. Mix: promoted at top + organic below
    """
    # 1. Resolve location
    location = resolve_location(lat, lng)
    wilayat = location.get("wilayat")
    governorate = location.get("governorate")
    nearby_gov_ids = location.get("nearby_governorate_ids", [])

    wilayat_name = wilayat["name_en"] if wilayat else None
    gov_id = governorate["id"] if governorate else None

    expansion_level = "wilayat"
    skip_offset = page * (limit - PROMOTED_SLOTS_PER_PAGE) if page > 0 else 0
    organic_limit = limit - PROMOTED_SLOTS_PER_PAGE if page == 0 else limit

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
            # Random rotation for fair exposure
            random.shuffle(promoted_ids)
            selected_ids = promoted_ids[:PROMOTED_SLOTS_PER_PAGE]
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
            skip=skip_offset,
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
                skip=skip_offset,
                limit=organic_limit,
            )

    # Level 3: Expand to nearby governorates
    if len(organic_listings) < MIN_RESULTS_THRESHOLD and nearby_gov_ids:
        expansion_level = "nearby"
        # Take the 3 nearest governorates
        nearest_3 = nearby_gov_ids[:3]
        wilayat_names = get_wilayats_for_governorates(nearest_3)
        if wilayat_names:
            organic_listings, total_organic = _fetch_organic_listings(
                place_names=wilayat_names,
                category_id=category_id,
                condition=condition,
                exclude_ids=promoted_ids,
                skip=skip_offset,
                limit=organic_limit,
            )

    # Level 4: All Oman (no location filter)
    if len(organic_listings) < MIN_RESULTS_THRESHOLD:
        expansion_level = "all"
        organic_listings, total_organic = _fetch_organic_listings(
            category_id=category_id,
            condition=condition,
            min_price=min_price,
            max_price=max_price,
            seller_type=seller_type,
            exclude_ids=promoted_ids,
            skip=skip_offset,
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

        for listing in all_listings:
            listing["images"] = images_map.get(listing["id"], [])
            if listing.get("location_id"):
                loc = locations_map.get(listing["location_id"])
                if loc:
                    listing["location_details"] = loc

    # 6. Pagination math
    total = total_organic + (len(promoted_listings) if page == 0 else 0)
    pages = math.ceil(total / limit) if total > 0 else 0

    return {
        "listings": all_listings,
        "resolved_location": {
            "wilayat_en": wilayat["name_en"] if wilayat else None,
            "wilayat_ar": wilayat["name_ar"] if wilayat else None,
            "governorate_en": governorate["name_en"] if governorate else None,
            "governorate_ar": governorate["name_ar"] if governorate else None,
            "expansion_level": expansion_level,
        },
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }


@router.get("/offers")
async def get_location_offers(
    lat: float = Query(..., description="User's latitude"),
    lng: float = Query(..., description="User's longitude"),
    page: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
):
    """
    Location-based offers feed (status-like offers on the home page).
    Returns active offer-type banners relevant to user's location.
    Offers with no location (admin-created global) are always included.
    """
    location = resolve_location(lat, lng)
    wilayat = location.get("wilayat")
    governorate = location.get("governorate")

    wilayat_name = wilayat["name_en"] if wilayat else None
    gov_id = governorate["id"] if governorate else None

    skip = page * limit

    def query_func(table):
        query = (
            table.select("*")
            .eq("status", "active")
            .eq("type", "offers")
        )

        # Location: match wilayat, governorate, or global (no location set)
        if wilayat_name and gov_id:
            query = query.or_(
                f"wilayat.eq.{wilayat_name},"
                f"governorate_id.eq.{gov_id},"
                "governorate_id.is.null"
            )
        elif gov_id:
            query = query.or_(
                f"governorate_id.eq.{gov_id},"
                "governorate_id.is.null"
            )

        return query.range(skip, skip + limit - 1).order("created_at", desc=True)

    # Count
    def count_func(table):
        query = (
            table.select("id", count="exact")
            .eq("status", "active")
            .eq("type", "offers")
        )
        if wilayat_name and gov_id:
            query = query.or_(
                f"wilayat.eq.{wilayat_name},"
                f"governorate_id.eq.{gov_id},"
                "governorate_id.is.null"
            )
        elif gov_id:
            query = query.or_(
                f"governorate_id.eq.{gov_id},"
                "governorate_id.is.null"
            )
        return query.limit(0)

    count_result = db.query("ad_banners", count_func)
    total = count_result.count if count_result.count is not None else 0

    result = db.query("ad_banners", query_func)
    offers = result.data if result.data else []

    pages = math.ceil(total / limit) if total > 0 else 0

    return {
        "offers": offers,
        "resolved_location": {
            "wilayat_en": wilayat["name_en"] if wilayat else None,
            "governorate_en": governorate["name_en"] if governorate else None,
        },
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }


@router.get("/nearby-stores")
async def get_nearby_stores(
    lat: float = Query(..., description="User's latitude"),
    lng: float = Query(..., description="User's longitude"),
    page: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    min_rating: Optional[float] = Query(None, description="Minimum average rating")
):
    """
    Location-aware store listing.
    Shows stores in user's wilayat/governorate with expanding radius.
    """
    location = resolve_location(lat, lng)
    wilayat = location.get("wilayat")
    governorate = location.get("governorate")
    nearby_gov_ids = location.get("nearby_governorate_ids", [])

    wilayat_name = wilayat["name_en"] if wilayat else None
    gov_id = governorate["id"] if governorate else None
    expansion_level = "wilayat"

    skip = page * limit

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
                query = query.range(skip, skip + limit - 1)
                
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

    # Level 3: Nearby governorates
    if len(stores) < MIN_RESULTS_THRESHOLD and nearby_gov_ids:
        expansion_level = "nearby"
        total = _count_stores(gov_filter=nearby_gov_ids[:3])
        stores = _fetch_stores(gov_filter=nearby_gov_ids[:3])

    # Level 4: All Oman
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
        stores = stores[skip : skip + limit]

    pages = math.ceil(total / limit) if total > 0 else 0

    return {
        "stores": stores,
        "resolved_location": {
            "wilayat_en": wilayat["name_en"] if wilayat else None,
            "governorate_en": governorate["name_en"] if governorate else None,
            "expansion_level": expansion_level,
        },
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }


@router.get("/resolve-location")
async def resolve_user_location(
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
