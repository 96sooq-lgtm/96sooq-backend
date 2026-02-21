from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
from models import schemas
from db.supabase_client import db
from utils.auth import get_current_admin

# Public Router
router = APIRouter(
    prefix="/api/offers",
    tags=["offers"]
)

# Admin Router
admin_router = APIRouter(
    prefix="/api/admin/offers",
    tags=["admin-offers"],
    dependencies=[Depends(get_current_admin)]
)


# -------------------------------------------------
# PUBLIC ENDPOINTS
# -------------------------------------------------

@router.get("/", response_model=List[schemas.OfferOut])
async def list_active_offers(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Public — no auth required.
    Returns all active offers with their media (images/videos).
    Used for promotional display in the app.
    """
    def query_func(table):
        return (
            table.select("*")
            .eq("status", "active")
            .range(skip, skip + limit - 1)
            .order("created_at", desc=True)
        )

    result = db.query("offers", query_func)
    return result.data if result.data else []


# -------------------------------------------------
# ADMIN ENDPOINTS
# -------------------------------------------------

@admin_router.post("/", response_model=schemas.OfferOut, status_code=status.HTTP_201_CREATED)
async def create_offer(payload: schemas.OfferCreate):
    """
    Admin: Create a new offer with multiple images/videos.
    media is a list of { url, type } objects where type is 'image' or 'video'.
    """
    data = {
        "title": payload.title,
        "title_ar": payload.title_ar,
        "description": payload.description,
        "images": payload.images,
        "status": "active",
    }

    offer = db.insert("offers", data)
    if not offer:
        raise HTTPException(status_code=500, detail="Failed to create offer")
    return offer


@admin_router.get("/", response_model=List[schemas.OfferOut])
async def list_all_offers_admin(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
):
    """
    Admin: List all offers with optional status filter.
    """
    def query_func(table):
        query = table.select("*")
        if status:
            query = query.eq("status", status)
        return query.range(skip, skip + limit - 1).order("created_at", desc=True)

    result = db.query("offers", query_func)
    return result.data if result.data else []


@admin_router.patch("/{offer_id}", response_model=schemas.OfferOut)
async def update_offer(offer_id: str, payload: schemas.OfferUpdate):
    """
    Admin: Update an offer. Only provided fields are updated.
    """
    offer = db.select_one("offers", offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    updates = payload.dict(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Serialize images list if provided
    if "images" in updates and updates["images"] is None:
        updates.pop("images")

    updated = db.update("offers", offer_id, updates)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update offer")
    return updated


@admin_router.put("/{offer_id}/deactivate", response_model=schemas.OfferOut)
async def deactivate_offer(offer_id: str):
    """Admin: Soft-hide an offer (status → inactive)."""
    offer = db.select_one("offers", offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    updated = db.update("offers", offer_id, {"status": "inactive"})
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to deactivate offer")
    return updated


@admin_router.delete("/{offer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_offer(offer_id: str):
    """Admin: Permanently delete an offer."""
    success = db.delete("offers", offer_id)
    if not success:
        raise HTTPException(status_code=404, detail="Offer not found")
