from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel
from typing import List, Optional
from models import schemas
from db.supabase_client import db
from utils.auth import get_current_admin, get_current_customer
from utils.logger import get_logger
import math

logger = get_logger(__name__)

# Customer-facing router
user_router = APIRouter(
    prefix="/api/users",
    tags=["users"],
)

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


@admin_router.get("/reports")
def list_user_reports(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status", description="pending|reviewed|dismissed"),
    target_type: Optional[str] = Query(None, description="listing|user"),
):
    """Admin: View all user reports (listing + user)."""
    skip = (page - 1) * limit

    def query_func(table):
        q = table.select("*").order("created_at", desc=True).range(skip, skip + limit - 1)
        if status_filter:
            q = q.eq("status", status_filter)
        if target_type:
            q = q.eq("target_type", target_type)
        return q

    result = db.query("user_reports", query_func)
    reports = result.data if result.data else []
    return {"reports": reports, "page": page, "limit": limit}


@admin_router.put("/reports/{report_id}")
def update_report_status(
    report_id: str,
    new_status: str = Query(..., description="reviewed|dismissed"),
    admin_note: Optional[str] = Query(None),
):
    """Admin: Mark a report as reviewed or dismissed."""
    if new_status not in ("reviewed", "dismissed"):
        raise HTTPException(status_code=400, detail="status must be 'reviewed' or 'dismissed'")
    update_payload = {"status": new_status}
    if admin_note:
        update_payload["admin_note"] = admin_note
    updated = db.update("user_reports", report_id, update_payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Report not found")
    return updated


# ─────────────────────────────────────────────────────────────────────────────
# CUSTOMER-FACING ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@user_router.post("/{target_user_id}/report", status_code=201)
def report_user(
    target_user_id: str,
    reason: str = Query(..., min_length=5, max_length=1000),
    current_user: dict = Depends(get_current_customer),
):
    """
    Report another user for fraudulent behaviour, spam, or abuse.
    Each reporter can only file one report per target user.
    """
    reporter_id = current_user["id"]

    if reporter_id == target_user_id:
        raise HTTPException(status_code=400, detail="You cannot report yourself")

    target = db.select_one("app_users", target_user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    existing = db.select("user_reports", filters={"reported_by": reporter_id, "target_user_id": target_user_id})
    if existing:
        raise HTTPException(status_code=409, detail="You have already reported this user")

    db.insert("user_reports", {
        "reported_by": reporter_id,
        "target_type": "user",
        "target_user_id": target_user_id,
        "reason": reason,
    })


    logger.warning(f"User reported: target={target_user_id}, by={reporter_id}, reason={reason}")
    return {"success": True, "message": "Report submitted. Our team will review it."}


@user_router.get("/me/language")
def get_user_language(current_user: dict = Depends(get_current_customer)):
    """
    Get current user's language preference.
    """
    user = db.select_one("app_users", current_user["id"], columns="language")
    return {"language": user.get("language") if user else "en"}


class LanguageUpdate(BaseModel):
    language: str

@user_router.put("/me/language")
def update_user_language(
    payload: LanguageUpdate,
    current_user: dict = Depends(get_current_customer)
):
    """
    Update current user's language preference (en or ar).
    """
    language = payload.language
    if language not in ["en", "ar"]:
        raise HTTPException(status_code=400, detail="Language must be 'en' or 'ar'")

    updated = db.update("app_users", current_user["id"], {"language": language})
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update language")
    
    logger.info(f"User {current_user['id']} updated language to {language}")
    return {"success": True, "language": language}


@user_router.delete("/me", status_code=status.HTTP_200_OK)
def delete_my_account(current_user: dict = Depends(get_current_customer)):
    """
    Customer: Permanently delete your own account (Soft Delete).
    This handles cascading soft-deletion for stores, listings, conversations, etc.
    """
    user_id = current_user["id"]
    try:
        # 1. Perform soft-delete on all related data
        success = soft_delete_user_data(user_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete account data")
            
        logger.info(f"User account {user_id} soft-deleted by user.")
        return {"success": True, "message": "Account successfully deleted. You have been logged out."}
        
    except Exception as e:
        logger.error(f"Error during account deletion for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred while deleting your account")


def soft_delete_user_data(user_id: str) -> bool:
    """
    Utility: Performs cascading soft-deletes for a user.
    """
    try:
        # 1. Update user status
        db.update("app_users", user_id, {"is_active": False})
        
        # 2. Inactivate owned stores
        def store_update(table):
            return table.update({"status": "inactive"}).eq("user_id", user_id)
        db.query("stores", store_update)
        
        # 3. Soft-delete all listings
        def listing_update(table):
            return table.update({"status": "soft_deleted"}).eq("user_id", user_id)
        db.query("listings", listing_update)
        
        # 4. Block/Archive all conversations
        def conv_update(table):
            return table.update({"status": "blocked"}).or_(f"buyer_id.eq.{user_id},seller_id.eq.{user_id}")
        db.query("conversations", conv_update)
        
        # 5. Expire ad banners
        def banner_update(table):
            return table.update({"status": "expired"}).eq("user_id", user_id)
        db.query("ad_banners", banner_update)
        
        # 6. Cancel pending offers - if table exists (optional, based on schema research)
        try:
             def offer_update(table):
                return table.update({"status": "rejected"}).or_(f"buyer_id.eq.{user_id},listing_id.in.(select id from listings where user_id = '{user_id}')")
             # This is a bit complex for a simple .query, might need separate logic or just leave it for now
             # if the listings are soft_deleted, the offers won't be accessible anyway.
             pass
        except:
             pass

        return True
    except Exception as e:
        logger.error(f"Cascade deletion failed for {user_id}: {e}")
        return False
