from fastapi import APIRouter, HTTPException, Depends, Query, status
from typing import List, Optional
from models import schemas
from db.supabase_client import db
from utils.auth import get_current_admin
from utils.logger import get_logger
import math

logger = get_logger(__name__)

# Admin Router to manage User app_users
admin_router = APIRouter(
    prefix="/api/admin/users",
    tags=["admin-users"],
    dependencies=[Depends(get_current_admin)]
)

@admin_router.get("/", response_model=schemas.AppUserAdminListResponse)
def list_app_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None
):
    """
    List app users with pagination and search.
    Returns basic details and whether they own an active store.
    """
    try:
        skip = (page - 1) * limit
        
        # 1. Fetch total count (optimized)
        def count_query(table):
            q = table.select("id", count="exact").limit(0)
            if search:
                # Search by name, phone_number, or email
                q = q.or_(f"name.ilike.%{search}%,phone_number.ilike.%{search}%,email.ilike.%{search}%")
            return q
            
        count_res = db.query("app_users", count_query)
        total = count_res.count or 0
        
        if total == 0:
            return {
                "users": [],
                "total": 0,
                "page": page,
                "limit": limit,
                "pages": 0
            }
            
        # 2. Fetch data
        def data_query(table):
            q = table.select("id, name, phone_number, email, is_active")
            if search:
                 q = q.or_(f"name.ilike.%{search}%,phone_number.ilike.%{search}%,email.ilike.%{search}%")
            return q.range(skip, skip + limit - 1).order("created_at", desc=True)
            
        result = db.query("app_users", data_query)
        users = result.data if result.data else []
        
        # 3. Check for stores 
        # Get all user IDs
        user_ids = [u["id"] for u in users]
        
        # Fetch active stores for these users in one query
        stores = []
        if user_ids:
            # We can't use select_in if the list is too huge, but with limit=20 it's fine
            stores = db.select_in("stores", "user_id", user_ids)
            
        # Map user_id -> has_store (boolean)
        active_store_owners = set(
            s["user_id"] for s in stores if s.get("status") in ["active", "pending_approval"]
        )
        
        # Format response
        formatted_users = []
        for user in users:
            formatted_users.append({
                "id": user["id"],
                "name": str(user.get("name") or "Unknown"),
                "phone_number": str(user.get("phone_number") or ""),
                "email": user.get("email"),
                "is_active": bool(user.get("is_active", True)),
                "is_store": user["id"] in active_store_owners
            })
            
        return {
            "users": formatted_users,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": math.ceil(total / limit)
        }
        
    except Exception as e:
        logger.error(f"Error fetching app users list: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve users")


@admin_router.get("/{user_id}", response_model=schemas.AppUserAdminDetail)
def get_app_user_details(user_id: str):
    """
    Get full details for a specific user, including store info and stats.
    """
    try:
        # 1. Get raw user
        user = db.select_one("app_users", user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        # 2. Check for Store
        stores = db.select("stores", filters={"user_id": user_id})
        is_store = False
        store_details = None
        
        if stores:
            is_store = True
            store = stores[0] # Usually 1 user = 1 store
            store_details = {
                "id": store["id"],
                "name": store["name"],
                "status": store["status"],
                "plan_id": store.get("plan_id"),
                "created_at": store.get("created_at")
            }
            
        # 3. Gather Stats (using count queries)
        def count_listings(table):
            return table.select("id", count="exact").eq("user_id", user_id).limit(0)
            
        def count_transactions(table):
            return table.select("id", count="exact").eq("user_id", user_id).limit(0)
            
        def sum_transactions(table):
            return table.select("amount").eq("user_id", user_id).eq("status", "success")

        listings_res = db.query("listings", count_listings)
        transactions_res = db.query("payments", count_transactions)
        revenue_res = db.query("payments", sum_transactions)
        
        total_revenue = 0.0
        if revenue_res.data:
            total_revenue = sum(float(p.get("amount", 0)) for p in revenue_res.data)
            
        stats = {
            "total_listings": listings_res.count or 0,
            "total_transactions": transactions_res.count or 0,
            "total_spend": round(total_revenue, 3)
        }
        
        # 4. Format and Return
        return {
            "id": user["id"],
            "name": str(user.get("name") or "Unknown"),
            "phone_number": str(user.get("phone_number") or ""),
            "email": user.get("email"),
            "is_active": bool(user.get("is_active", True)),
            "provider": user.get("provider"),
            "profile_picture": user.get("profile_picture"),
            "created_at": user.get("created_at"),
            "updated_at": user.get("updated_at"),
            "is_store": is_store,
            "store_details": store_details,
            "stats": stats
        }
        
    except HTTPException:
         raise
    except Exception as e:
        logger.error(f"Error fetching user details {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve user details")


@admin_router.put("/{user_id}/status")
def toggle_user_status(user_id: str, is_active: bool = Query(...)):
    """
    Admin block/unblock a user.
    """
    try:
        user = db.select_one("app_users", user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        updated = db.update("app_users", user_id, {"is_active": is_active})
        if not updated:
            raise HTTPException(status_code=500, detail="Failed to update user status")
            
        status_text = "activated" if is_active else "blocked"
        logger.info(f"User {user_id} was {status_text} by admin")
        
        return {"message": f"User successfully {status_text}", "is_active": is_active}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling user status {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update user status")
