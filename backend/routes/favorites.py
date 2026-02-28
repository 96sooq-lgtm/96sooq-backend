from fastapi import APIRouter, HTTPException, status, Depends, Query
from models import schemas
from db.supabase_client import db
from utils.auth import get_current_customer
from utils.logger import get_logger
from typing import List

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/favorites",
    tags=["favorites"],
    dependencies=[Depends(get_current_customer)]
)


@router.post("/{listing_id}", status_code=status.HTTP_200_OK)
async def toggle_favorite(
    listing_id: str,
    current_user: dict = Depends(get_current_customer)
):
    """
    Toggle a listing as favorite.
    - If not favorited → adds it, returns { is_favorited: true }
    - If already favorited → removes it, returns { is_favorited: false }
    """
    user_id = current_user["id"]

    # Verify listing exists
    listing = db.select_one("listings", listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Check if already favorited
    existing = db.select("favorites", filters={
        "user_id": user_id,
        "listing_id": listing_id,
    })

    if existing:
        # Already favorited → remove
        db.delete("favorites", existing[0]["id"])
        return {"is_favorited": False, "listing_id": listing_id}

    # Not favorited → add
    fav = db.insert("favorites", {
        "user_id": user_id,
        "listing_id": listing_id,
    })
    if not fav:
        raise HTTPException(status_code=500, detail="Failed to add favorite")

    return {"is_favorited": True, "listing_id": listing_id}


@router.delete("/{listing_id}", status_code=status.HTTP_200_OK)
async def remove_favorite(
    listing_id: str,
    current_user: dict = Depends(get_current_customer)
):
    """
    Explicitly remove a listing from favorites.
    """
    user_id = current_user["id"]

    existing = db.select("favorites", filters={
        "user_id": user_id,
        "listing_id": listing_id,
    })

    if not existing:
        raise HTTPException(status_code=404, detail="Favorite not found")

    db.delete("favorites", existing[0]["id"])
    return {"is_favorited": False, "listing_id": listing_id}


@router.get("/", response_model=schemas.FavoriteListResponse)
async def list_favorites(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_customer)
):
    """
    List all favorite listings for the authenticated user.
    Returns the full listing details (not just IDs).
    """
    import math
    user_id = current_user["id"]

    # Count total favorites
    def count_func(table):
        return table.select("id", count="exact").eq("user_id", user_id)

    count_result = db.query("favorites", count_func)
    total = count_result.count if count_result.count is not None else 0

    # Get favorite records (paginated)
    def query_func(table):
        return (
            table.select("*")
            .eq("user_id", user_id)
            .range(skip, skip + limit - 1)
            .order("created_at", desc=True)
        )

    result = db.query("favorites", query_func)
    favorites = result.data if result.data else []

    # Batch fetch listing details — 1 query instead of N
    listings = []
    if favorites:
        from utils.helpers import batch_listing_images

        listing_ids = [fav["listing_id"] for fav in favorites]
        all_listings = db.select_in("listings", "id", listing_ids)
        listings_map = {l["id"]: l for l in all_listings}

        # Batch fetch images — 1 query instead of N
        images_map = batch_listing_images(listing_ids)

        # Build favorited_at lookup
        fav_dates = {fav["listing_id"]: fav.get("created_at") for fav in favorites}

        for lid in listing_ids:
            listing = listings_map.get(lid)
            if listing:
                listing["images"] = images_map.get(lid, [])
                listing["favorited_at"] = fav_dates.get(lid)
                listings.append(listing)

    page = (skip // limit) + 1 if limit else 1
    pages = math.ceil(total / limit) if limit and total else 0

    return {
        "listings": listings,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
    }


@router.get("/check/{listing_id}")
async def check_favorite(
    listing_id: str,
    current_user: dict = Depends(get_current_customer)
):
    """
    Check if a specific listing is favorited by the current user.
    Useful for the UI to show the heart icon state.
    """
    existing = db.select("favorites", filters={
        "user_id": current_user["id"],
        "listing_id": listing_id,
    })
    return {"is_favorited": bool(existing), "listing_id": listing_id}
