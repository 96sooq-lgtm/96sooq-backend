from fastapi import APIRouter, HTTPException, status, Depends, Query
from models import schemas
from db.supabase_client import db
from utils.auth import get_current_customer, get_current_admin
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


@router.get("/", response_model=List[schemas.StoreOut])
async def list_stores(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    user_id: Optional[str] = None
):
    """
    List active stores.
    If user_id is provided, list user's stores (even if pending/rejected for that user? 
    Usually public listing only shows active. User's own view should be different).
    """
    def query_func(table):
        query = table.select("*")
        
        if user_id:
             # If filtering by user, return all statuses (so they can see their pending stores)
            query = query.eq("user_id", user_id)
        else:
            # Public view: only active stores
            query = query.eq("status", "active")
            
        return query.range(skip, skip + limit - 1).order("created_at", desc=True)

    result = db.query("stores", query_func)
    return result.data if result.data else []


@router.get("/{store_id}", response_model=schemas.StoreOut)
async def get_store(store_id: str):
    store = db.select_one("stores", store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
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
    # User cannot change status directly via this endpoint usually, 
    # but maybe they can "close" it? For now, ignore status updates from user.
    if "status" in update_data:
        del update_data["status"]
        
    updated = db.update("stores", store_id, update_data)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update store")
        
    return updated


# -------------------------------------------------
# ADMIN ENDPOINTS
# -------------------------------------------------

@admin_router.get("/", response_model=List[schemas.StoreOut])
async def list_all_stores_admin(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None
):
    """
    Admin: List all stores with optional status filter.
    """
    def query_func(table):
        query = table.select("*")
        if status:
            query = query.eq("status", status)
        return query.range(skip, skip + limit - 1).order("created_at", desc=True)

    result = db.query("stores", query_func)
    return result.data if result.data else []


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
