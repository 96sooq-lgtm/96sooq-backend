from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from models import schemas
from db.supabase_client import db
from utils.auth import get_current_customer, get_current_admin, decode_customer_token
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


@router.get("/", response_model=List[schemas.StoreOut])
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
        query = table.select("*")
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

@admin_router.put("/{store_id}/lock")
async def lock_store(store_id: str):
    """
    Admin: Soft-lock a store. Status → 'locked'.
    - Hidden from all public listings immediately
    - Store data is preserved (not deleted)
    - Owner can still log in but their store won't be visible
    - Can be unlocked at any time with /unlock
    """
    store = db.select_one("stores", store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    updated = db.update("stores", store_id, {"status": "locked"})
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to lock store")
    return updated

@admin_router.put("/{store_id}/unlock")
async def unlock_store(store_id: str):
    """
    Admin: Unlock a previously locked store. Status → 'active'.
    """
    store = db.select_one("stores", store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    updated = db.update("stores", store_id, {"status": "active"})
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to unlock store")
    return updated
