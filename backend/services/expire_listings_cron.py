"""
Background cron: automatically expires listings and subscriptions
whose expiry date has passed.

Runs every 10 minutes within the FastAPI lifespan.
"""
import asyncio
from datetime import datetime
from db.supabase_client import db
from utils.logger import get_logger

logger = get_logger("expire_listings_cron")

INTERVAL_SECONDS = 24 * 60 * 60  # 24 hours (once per day)


def _expire_listings() -> int:
    """
    Find all listings where status='active' and expires_at < now,
    then update their status to 'expired'.
    Returns the number of listings expired.
    """
    now_iso = datetime.utcnow().isoformat()

    # Fetch active listings that have passed their expiry
    def query_func(table):
        return (
            table.select("id, title, user_id, expires_at")
            .eq("status", "active")
            .not_.is_("expires_at", "null")
            .lt("expires_at", now_iso)
            .limit(200)
        )

    result = db.query("listings", query_func)
    expired_listings = result.data if result.data else []

    if not expired_listings:
        return 0

    count = 0
    for listing in expired_listings:
        try:
            db.update("listings", listing["id"], {"status": "expired"})
            logger.info(
                f"Listing expired: id={listing['id']}, "
                f"title='{listing.get('title', '?')}', "
                f"user={listing.get('user_id', '?')}, "
                f"expires_at={listing.get('expires_at')}"
            )
            count += 1
        except Exception as e:
            logger.error(f"Failed to expire listing {listing['id']}: {e}")

    return count


def _expire_subscriptions() -> int:
    """
    Find all user_subscriptions where status='active' and end_date < now,
    then update their status to 'expired'.
    Returns the number of subscriptions expired.
    """
    now_iso = datetime.utcnow().isoformat()

    def query_func(table):
        return (
            table.select("id, user_id, plan_id, end_date")
            .eq("status", "active")
            .lt("end_date", now_iso)
            .limit(200)
        )

    result = db.query("user_subscriptions", query_func)
    expired_subs = result.data if result.data else []

    if not expired_subs:
        return 0

    count = 0
    for sub in expired_subs:
        try:
            db.update("user_subscriptions", sub["id"], {"status": "expired"})
            logger.info(
                f"Subscription expired: id={sub['id']}, "
                f"user={sub.get('user_id', '?')}, "
                f"plan={sub.get('plan_id', '?')}, "
                f"end_date={sub.get('end_date')}"
            )
            count += 1
        except Exception as e:
            logger.error(f"Failed to expire subscription {sub['id']}: {e}")

    return count


async def run_expiry_cron():
    """
    Async loop that runs the expiry checks every INTERVAL_SECONDS.
    Designed to be launched as a background task in the FastAPI lifespan.
    """
    logger.info(f"Expiry cron started (interval={INTERVAL_SECONDS}s)")

    while True:
        try:
            listings_count = _expire_listings()
            subs_count = _expire_subscriptions()

            if listings_count or subs_count:
                logger.info(
                    f"Expiry cron cycle complete: "
                    f"{listings_count} listing(s), {subs_count} subscription(s) expired"
                )
        except Exception as e:
            logger.error(f"Expiry cron error: {type(e).__name__}: {e}", exc_info=True)

        await asyncio.sleep(INTERVAL_SECONDS)
