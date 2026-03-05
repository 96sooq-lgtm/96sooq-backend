"""
Notification Routes — 96sooq
Handles device token registration and notification history retrieval.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional
from db.supabase_client import db
from utils.auth import get_current_customer
from utils.logger import get_logger
import math

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/notifications",
    tags=["notifications"],
)


# ── Schemas ──────────────────────────────────────────────────────────────────

class RegisterTokenRequest(BaseModel):
    fcm_token: str
    device_type: str = "mobile"   # 'mobile' or 'web'
    device_name: Optional[str] = None


class UnregisterTokenRequest(BaseModel):
    fcm_token: str


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/register-token", summary="Register an FCM device token")
def register_device_token(
    payload: RegisterTokenRequest,
    current_user: dict = Depends(get_current_customer),
):
    """
    Called on app launch / login to register the device's FCM token.
    Idempotent: re-registers (upserts) the same token without duplicating.
    """
    user_id = current_user["id"]

    if not payload.fcm_token or len(payload.fcm_token) < 10:
        raise HTTPException(status_code=400, detail="Invalid FCM token")

    # Check if token already exists for this user
    existing = db.select("device_tokens", filters={"user_id": user_id, "fcm_token": payload.fcm_token})

    if existing:
        # Re-activate if it was deactivated
        if not existing[0].get("is_active"):
            db.update("device_tokens", existing[0]["id"], {
                "is_active": True,
                "device_type": payload.device_type,
                "device_name": payload.device_name,
            })
            logger.info(f"Device token re-activated: user={user_id}")
        return {"success": True, "message": "Token already registered"}

    # Check if this token belongs to another user (device switched accounts)
    other_user_token = db.select("device_tokens", filters={"fcm_token": payload.fcm_token})
    if other_user_token:
        # Deactivate old owner's token
        db.update("device_tokens", other_user_token[0]["id"], {"is_active": False})
        logger.info(f"Token transferred from user {other_user_token[0]['user_id']} to {user_id}")

    # Insert new token
    db.insert("device_tokens", {
        "user_id": user_id,
        "fcm_token": payload.fcm_token,
        "device_type": payload.device_type,
        "device_name": payload.device_name,
        "is_active": True,
    })

    logger.info(f"Device token registered: user={user_id}, type={payload.device_type}")
    return {"success": True, "message": "Token registered"}


@router.delete("/unregister-token", summary="Unregister an FCM device token")
def unregister_device_token(
    payload: UnregisterTokenRequest,
    current_user: dict = Depends(get_current_customer),
):
    """Called on logout to stop sending push notifications to this device."""
    user_id = current_user["id"]

    existing = db.select("device_tokens", filters={"user_id": user_id, "fcm_token": payload.fcm_token})
    if existing:
        db.update("device_tokens", existing[0]["id"], {"is_active": False})
        logger.info(f"Device token deactivated on logout: user={user_id}")

    return {"success": True, "message": "Token unregistered"}


@router.get("/", summary="Get notification history for the current user")
def get_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_customer),
):
    """Returns notification history, newest first, with pagination."""
    user_id = current_user["id"]

    def query_func(table):
        return (
            table.select("*", count="exact")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(skip, skip + limit - 1)
        )

    result = db.query("notifications", query_func)
    items = result.data if result.data else []
    total = result.count if result.count is not None else len(items)
    pages = math.ceil(total / limit) if total > 0 else 0

    return {
        "notifications": items,
        "total": total,
        "page": (skip // limit) + 1,
        "limit": limit,
        "pages": pages,
    }


@router.get("/unread-count", summary="Get count of unread notifications")
def get_unread_count(
    current_user: dict = Depends(get_current_customer),
):
    """Returns the number of unread notifications for badge display."""
    user_id = current_user["id"]

    def query_func(table):
        return (
            table.select("id", count="exact")
            .eq("user_id", user_id)
            .eq("is_read", False)
            .limit(0)
        )

    result = db.query("notifications", query_func)
    return {"unread_count": result.count or 0}


@router.post("/{notification_id}/read", summary="Mark a single notification as read")
def mark_notification_read(
    notification_id: str,
    current_user: dict = Depends(get_current_customer),
):
    """Marks a notification as read."""
    user_id = current_user["id"]
    notif = db.select_one("notifications", notification_id)

    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notif["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    db.update("notifications", notification_id, {"is_read": True})
    return {"success": True}


@router.post("/mark-all-read", summary="Mark all notifications as read")
def mark_all_read(
    current_user: dict = Depends(get_current_customer),
):
    """Marks all unread notifications as read for the current user."""
    user_id = current_user["id"]

    try:
        client = db.get_client()
        client.table("notifications").update({"is_read": True}).eq("user_id", user_id).eq("is_read", False).execute()
        logger.info(f"All notifications marked as read: user={user_id}")
    except Exception as e:
        logger.error(f"Failed to mark all as read: {e}")
        raise HTTPException(status_code=500, detail="Failed to update notifications")

    return {"success": True, "message": "All notifications marked as read"}
