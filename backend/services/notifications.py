from db.supabase_client import db
from utils.fcm import send_push_to_multiple
from utils.logger import get_logger
from datetime import datetime

logger = get_logger(__name__)

# -----------------------------------------------------------------------------
# TRANSLATIONS
# -----------------------------------------------------------------------------
MESSAGES = {
    "payment_success": {
        "title": {"en": "Payment Successful ✅", "ar": "تم الدفع بنجاح ✅"},
        "body": {
            "en": "Your listing \"{listing_title}\" has been submitted for review. Amount: {amount} {currency}",
            "ar": "تم تقديم إعلانك \"{listing_title}\" للمراجعة. المبلغ: {amount} {currency}"
        }
    },
    "listing_approved": {
        "title": {"en": "Listing Approved 🎉", "ar": "تمت الموافقة على الإعلان 🎉"},
        "body": {
            "en": "Your listing \"{listing_title}\" is now live! Buyers can see it on 96sooq.",
            "ar": "إعلانك \"{listing_title}\" مباشر الآن! يمكن للمشترين رؤيته على 96sooq."
        }
    },
    "listing_rejected": {
        "title": {"en": "Listing Rejected ❌", "ar": "تم رفض الإعلان ❌"},
        "body": {
            "en": "Your listing \"{listing_title}\" was not approved. Reason: {reason}",
            "ar": "لم تتم الموافقة على إعلانك \"{listing_title}\". السبب: {reason}"
        }
    },
    "new_message": {
        "title": {"en": "New message from {sender_name}", "ar": "رسالة جديدة من {sender_name}"},
        "body": {
            "en": "{message_preview}",
            "ar": "{message_preview}"
        }
    },
    "store_limit_reached": {
        "title": {"en": "Listing Limit Reached ⚠️", "ar": "تم الوصول إلى الحد الأقصى للإعلانات ⚠️"},
        "body": {
            "en": "You have reached your listing limit for this plan. Please upgrade your subscription to post more.",
            "ar": "لقد وصلت إلى الحد الأقصى للإعلانات لهذه الخطة. يرجى ترقية اشتراكك لنشر المزيد."
        }
    }
}

# -----------------------------------------------------------------------------
# INTERNAL HELPERS
# -----------------------------------------------------------------------------

def _get_user_tokens(user_id: str) -> list[str]:
    tokens = db.select("device_tokens", columns="fcm_token", filters={"user_id": user_id, "is_active": True})
    return [t["fcm_token"] for t in tokens] if tokens else []


def _deactivate_tokens(tokens: list[str]):
    if not tokens: return
    for token in tokens:
        try:
            db.get_client().table("device_tokens").update({"is_active": False}).eq("fcm_token", token).execute()
        except Exception as e:
            logger.warning(f"Failed to deactivate token: {e}")


def _save_notification(user_id: str, title: str, body: str, notif_type: str, data: dict | None = None):
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


def _send_notification(user_id: str, notif_type: str, data: dict | None = None, **kwargs):
    """
    Main dispatcher with localization and deep linking.
    """
    # 1. Get User Language
    user = db.select_one("app_users", user_id, columns="language")
    lang = (user.get("language") or "en") if user else "en"

    # 2. Get Translated Content
    tpl = MESSAGES.get(notif_type)
    if not tpl:
        logger.error(f"Unknown notification type: {notif_type}")
        return

    title_tpl = tpl["title"].get(lang, tpl["title"]["en"])
    body_tpl = tpl["body"].get(lang, tpl["body"]["en"])

    title = title_tpl.format(**kwargs)
    body = body_tpl.format(**kwargs)

    # limit body length
    if len(body) > 200: body = body[:197] + "..."

    # 3. Save to history
    _save_notification(user_id, title, body, notif_type, data)

    # 4. Fetch tokens
    tokens = _get_user_tokens(user_id)
    if not tokens:
        logger.info(f"No tokens for user {user_id} - notification saved locally only.")
        return

    # 5. Prepare Payload for Deep Linking
    # Standard keys expected by frontend: screen, listing_id, conversation_id
    push_data = {
        "type": notif_type,
        "click_action": "FLUTTER_NOTIFICATION_CLICK",
        "sound": "default",
        "status": "done",
        **(data or {}),
    }

    failed = send_push_to_multiple(tokens, title, body, data=push_data)
    if failed:
        _deactivate_tokens(failed)


# -----------------------------------------------------------------------------
# PUBLIC API
# -----------------------------------------------------------------------------

def notify_payment_success(user_id: str, listing_id: str, listing_title: str, amount: float, currency: str):
    data = {"listing_id": listing_id, "screen": "my_listings"}
    _send_notification(user_id, "payment_success", data, listing_title=listing_title, amount=amount, currency=currency)


def notify_listing_approved(user_id: str, listing_id: str, listing_title: str):
    data = {"listing_id": listing_id, "screen": "listing_detail"}
    _send_notification(user_id, "listing_approved", data, listing_title=listing_title)


def notify_listing_rejected(user_id: str, listing_id: str, listing_title: str, reason: str):
    data = {"listing_id": listing_id, "screen": "my_listings"}
    _send_notification(user_id, "listing_rejected", data, listing_title=listing_title, reason=reason)


def notify_new_message(receiver_id: str, sender_name: str, conversation_id: str, listing_id: str, message_preview: str):
    data = {
        "conversation_id": conversation_id,
        "listing_id": listing_id,
        "screen": "chat"
    }
    preview = message_preview if message_preview else "You have a new message"
    _send_notification(receiver_id, "new_message", data, sender_name=sender_name, message_preview=preview)

def notify_store_limit_reached(user_id: str):
    """Notify store user that they reached their listing limit."""
    data = {"screen": "subscription_plans"}
    _send_notification(user_id, "store_limit_reached", data)
