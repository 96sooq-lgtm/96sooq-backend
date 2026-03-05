"""
Notification Service — 96sooq
Business logic for sending push notifications via FCM.
Handles token lookup, notification persistence, and stale token cleanup.
"""
from db.supabase_client import db
from utils.fcm import send_push_to_multiple
from utils.logger import get_logger

logger = get_logger(__name__)


def _get_user_tokens(user_id: str) -> list[str]:
    """Fetch all active FCM tokens for a user."""
    tokens = db.select("device_tokens", columns="fcm_token", filters={"user_id": user_id, "is_active": True})
    return [t["fcm_token"] for t in tokens] if tokens else []


def _deactivate_tokens(tokens: list[str]):
    """Mark stale/invalid tokens as inactive so we stop sending to them."""
    if not tokens:
        return
    for token in tokens:
        try:
            client = db.get_client()
            client.table("device_tokens").update({"is_active": False}).eq("fcm_token", token).execute()
        except Exception as e:
            logger.warning(f"Failed to deactivate token: {e}")


def _save_notification(user_id: str, title: str, body: str, notif_type: str, data: dict | None = None):
    """Persist notification in the notifications table for in-app history."""
    try:
        db.insert("notifications", {
            "user_id": user_id,
            "title": title,
            "body": body,
            "type": notif_type,
            "data": data or {},
        })
    except Exception as e:
        logger.warning(f"Failed to save notification: {e}")


def _send_notification(user_id: str, title: str, body: str, notif_type: str, data: dict | None = None):
    """
    Core notification dispatcher.
    1. Save to DB (notification history)
    2. Fetch user device tokens
    3. Send FCM push to all devices
    4. Clean up stale tokens
    """
    # 1. Save to notification history
    _save_notification(user_id, title, body, notif_type, data)

    # 2. Get device tokens
    tokens = _get_user_tokens(user_id)
    if not tokens:
        logger.info(f"No device tokens for user {user_id} — notification saved but not pushed")
        return

    # 3. Send push
    push_data = {
        "type": notif_type,
        "click_action": "FLUTTER_NOTIFICATION_CLICK",
        **(data or {}),
    }

    failed = send_push_to_multiple(tokens, title, body, data=push_data)

    # 4. Clean up stale tokens
    if failed:
        _deactivate_tokens(failed)
        logger.info(f"Deactivated {len(failed)} stale token(s) for user {user_id}")


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API — called from route handlers
# ─────────────────────────────────────────────────────────────────────────────

def notify_payment_success(user_id: str, listing_id: str, listing_title: str, amount: float, currency: str):
    """
    Trigger 1: After successful payment → listing sent to admin for approval.
    """
    title = "Payment Successful ✅"
    body = f"Your listing \"{listing_title}\" has been submitted for review. Amount: {amount} {currency}"
    data = {
        "listing_id": listing_id,
        "screen": "my_listings",
    }
    try:
        _send_notification(user_id, title, body, "payment_success", data)
        logger.info(f"Payment success notification sent: user={user_id}, listing={listing_id}")
    except Exception as e:
        logger.error(f"Failed to send payment notification: {e}")


def notify_listing_approved(user_id: str, listing_id: str, listing_title: str):
    """
    Trigger 2: When admin approves the listing.
    """
    title = "Listing Approved 🎉"
    body = f"Your listing \"{listing_title}\" is now live! Buyers can see it on 96sooq."
    data = {
        "listing_id": listing_id,
        "screen": "listing_detail",
    }
    try:
        _send_notification(user_id, title, body, "listing_approved", data)
        logger.info(f"Listing approved notification sent: user={user_id}, listing={listing_id}")
    except Exception as e:
        logger.error(f"Failed to send listing approved notification: {e}")


def notify_new_message(
    receiver_id: str,
    sender_name: str,
    conversation_id: str,
    listing_id: str,
    message_preview: str,
):
    """
    Trigger 3: When a user receives a new chat message.
    """
    title = f"New message from {sender_name}"
    body = message_preview[:200] if message_preview else "You have a new message"
    data = {
        "conversation_id": conversation_id,
        "listing_id": listing_id,
        "screen": "chat",
    }
    try:
        _send_notification(receiver_id, title, body, "new_message", data)
        logger.info(f"New message notification sent: receiver={receiver_id}, conv={conversation_id}")
    except Exception as e:
        logger.error(f"Failed to send message notification: {e}")
