from fastapi import APIRouter, HTTPException, Depends, status, Request, BackgroundTasks, Query
from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from db.supabase_client import db
from utils.auth import get_current_customer, get_current_admin
from utils.paymob import PaymobManager
from utils.logger import get_logger
from config.settings import settings
import uuid
import json
import math
from datetime import datetime, timedelta
from models import schemas

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/payments",
    tags=["payments"]
)

admin_router = APIRouter(
    prefix="/api/admin/payments",
    tags=["admin-payments"],
    dependencies=[Depends(get_current_admin)]
)

# Initialize Paymob Manager
paymob = PaymobManager()

# Schemas
class CheckoutItem(BaseModel):
    listing_id: str
    listing_plan_id: Optional[str] = None # Optional if using existing quota? No, front sends what user selected.
    use_existing_quota: Optional[bool] = False
    ad_plan_id: Optional[str] = None
    ad_duration_days: Optional[int] = 1
    currency: str = "OMR" 

class CheckoutResponse(BaseModel):
    status: str # 'success' (for free/quota) or 'payment_initiated'
    transaction_id: str
    payment_url: Optional[str] = None # Intention API returns a redirect URL
    message: Optional[str] = None

class WebhookCallback(BaseModel):
    # Depending on how Paymob sends data (QueryParams or Body)
    pass

# Helper to activate bundle
async def activate_bundle(payment_id: str, metadata: dict, user_id: str):
    """
    Activates the items in the bundle (Listing and/or Ad) after successful payment.
    Called by the webhook after payment confirmation.
    Metadata contains: listing_id, listing_plan_id, ad_plan_id.
    """
    logger.info(f"Activating bundle for payment={payment_id}, user={user_id}")

    listing_id      = metadata.get("listing_id")
    listing_plan_id = metadata.get("listing_plan_id")
    ad_plan_id      = metadata.get("ad_plan_id")
    now             = datetime.utcnow()

    try:
        # ── 1. Activate Listing ───────────────────────────────────────────────
        if listing_id:
            listing_expires_at = None

            # a) Create new subscription from the purchased plan
            if listing_plan_id:
                plan = db.select_one("pricing_plans", listing_plan_id)
                if plan:
                    days  = plan.get("duration_days", 30)
                    quota = plan.get("quota", 0)
                    end_date = (now + timedelta(days=days)).isoformat()
                    listing_expires_at = end_date

                    remaining_quota = (quota - 1) if quota > 0 else (quota if quota == -1 else 0)
                    db.insert("user_subscriptions", {
                        "user_id":          user_id,
                        "plan_id":          listing_plan_id,
                        "start_date":       now.isoformat(),
                        "end_date":         end_date,
                        "remaining_quota":  remaining_quota,
                        "status":           "active",
                    })
                    logger.info(f"Subscription created: plan={listing_plan_id}, quota_remaining={remaining_quota}")

            # b) Or deduct from existing subscription
            elif metadata.get("use_existing_quota"):
                def sub_query(table):
                    return (
                        table.select("*")
                        .eq("user_id", user_id)
                        .eq("status", "active")
                        .gte("end_date", now.isoformat())
                        .order("end_date", desc=True)
                        .limit(1)
                    )
                sub_result  = db.query("user_subscriptions", sub_query)
                active_sub  = sub_result.data[0] if sub_result.data else None

                if active_sub:
                    remaining = active_sub.get("remaining_quota", 0)
                    if remaining > 0:
                        db.update("user_subscriptions", active_sub["id"], {"remaining_quota": remaining - 1})
                        logger.info(f"Deducted quota from subscription {active_sub['id']}. New remaining={remaining - 1}")
                    listing_expires_at = active_sub.get("end_date")

            # Move listing to pending_approval (works for both new and renewal)
            listing_update = {"status": "pending_approval"}
            if listing_expires_at:
                listing_update["expires_at"] = listing_expires_at
            db.update("listings", listing_id, listing_update)
            logger.info(f"Listing {listing_id} moved to pending_approval (expires_at={listing_expires_at})")

            # ── Push Notification: payment success → listing under review ──
            try:
                from services.notifications import notify_payment_success

                # Fetch listing + payment in one place (payment_record reused below)
                listing_data   = db.select_one("listings", listing_id)
                payment_record = db.select_one("payments", payment_id)

                listing_title = (listing_data or {}).get("title", "Your listing")
                amount        = (payment_record or {}).get("amount", 0)
                currency      = (payment_record or {}).get("currency", "OMR")

                notify_payment_success(user_id, listing_id, listing_title, amount, currency)
            except Exception as notif_err:
                logger.warning(f"Payment notification failed (non-blocking): {notif_err}")

        # ── 2. Activate Ad Boost ──────────────────────────────────────────────
        if ad_plan_id:
            ad_duration_days = metadata.get("ad_duration_days", 1)

            # Check if an active promotion for this plan+listing already exists
            def promo_query(table):
                return (
                    table.select("id, end_date")
                    .eq("listing_id", listing_id)
                    .eq("plan_id", ad_plan_id)
                    .eq("status", "active")
                    .gte("end_date", now.isoformat())
                    .limit(1)
                )
            promo_result   = db.query("listing_promotions", promo_query)
            existing_promo = promo_result.data[0] if promo_result.data else None

            if existing_promo:
                # Extend from current end_date to avoid creating a duplicate
                try:
                    current_end = datetime.fromisoformat(
                        existing_promo["end_date"].replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                except Exception:
                    current_end = now

                ad_end_date = (current_end + timedelta(days=ad_duration_days)).isoformat()
                db.update("listing_promotions", existing_promo["id"], {"end_date": ad_end_date})
                logger.info(f"Ad boost {ad_plan_id} extended for listing {listing_id} to {ad_end_date}")
            else:
                # Create as 'pending' — activated with fresh dates on admin approval
                ad_end_date = (now + timedelta(days=ad_duration_days)).isoformat()
                db.insert("listing_promotions", {
                    "listing_id": listing_id,
                    "plan_id":    ad_plan_id,
                    "start_date": now.isoformat(),
                    "end_date":   ad_end_date,
                    "status":     "pending",
                })
                logger.info(
                    f"Ad boost {ad_plan_id} created as pending for listing {listing_id} "
                    f"({ad_duration_days} days — starts at approval)"
                )

            # ── 3. Sync with ad_banners for Banner/Offers feed ──
            ad_plan = db.select_one("pricing_plans", ad_plan_id)
            if ad_plan and ad_plan.get("type") == "ad" and ad_plan.get("ad_sub_type") in (
                "offers", "product_listing", "chat_screen"
            ):
                listing = db.select_one("listings", listing_id)
                if listing:
                    sub_type_map = {
                        "offers":           "top_offers",
                        "product_listing":  "product_listing",
                        "chat_screen":      "chat_screen",
                    }
                    banner_type = sub_type_map[ad_plan["ad_sub_type"]]
                    images      = listing.get("images") or []

                    banner_data = {
                        "user_id":        user_id,
                        "listing_id":     listing_id,
                        "type":           banner_type,
                        "name":           listing.get("title", "Boosted Listing"),
                        "image_url":      images[0] if images else "",
                        "status":         "pending_approval",
                        "expires_at":     ad_end_date,
                        "governorate_id": listing.get("location_id"),
                        "wilayat":        listing.get("place"),
                        "plan_id":        ad_plan_id,
                    }

                    existing_banners = db.select("ad_banners", filters={"listing_id": listing_id, "type": banner_type})
                    if existing_banners:
                        db.update("ad_banners", existing_banners[0]["id"], banner_data)
                    else:
                        db.insert("ad_banners", banner_data)

                    logger.info(f"Banner synced for listing {listing_id} (type={banner_type}, expires={ad_end_date})")

        # ── Mark payment success ──────────────────────────────────────────────
        db.update("payments", payment_id, {"status": "success"})
        logger.info(f"Payment {payment_id} marked as success")

    except Exception as e:
        logger.error(
            f"Bundle activation error for payment {payment_id}: {type(e).__name__}: {e}",
            exc_info=True,
        )
        # FIX: 'failed_activation' violates the payments_status_check DB constraint → use 'failed'
        db.update("payments", payment_id, {"status": "failed"})

@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    payload: CheckoutItem,
    current_user: dict = Depends(get_current_customer)
):
    """
    Unified Checkout for Listing + Ads.
    All listings require a paid subscription plan — no free listings.
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user token")

    logger.info(f"Checkout initiated: user={user_id}, listing={payload.listing_id}, plan={payload.listing_plan_id}")

    # 1. Validate Listing
    listing = db.select_one("listings", payload.listing_id)
    if not listing:
        logger.warning(f"Checkout failed: listing '{payload.listing_id}' not found")
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.get("user_id") != user_id:
        logger.warning(f"Checkout failed: user {user_id} does not own listing {payload.listing_id}")
        raise HTTPException(status_code=403, detail="You can only checkout your own listings")

    # Guard: if there is already a pending payment for this listing, return it
    # This prevents double-charges from rapid double-taps on the Pay button
    existing_pending = db.select("payments", filters={"user_id": user_id, "status": "pending"})
    for ep in (existing_pending or []):
        try:
            ep_meta = ep.get("metadata", {})
            if isinstance(ep_meta, str):
                import json as _json
                ep_meta = _json.loads(ep_meta)
        except Exception:
            ep_meta = {}
        if ep_meta.get("listing_id") == payload.listing_id:
            logger.info(f"Double-tap guard: returning existing pending payment {ep['id']} for listing {payload.listing_id}")
            return {
                "status": "payment_initiated",
                "transaction_id": ep["id"],
                "payment_url": None,  # frontend should already have URL; re-trigger via /checkout again after expiry
                "message": "A payment for this listing is already in progress. Please complete or cancel it first.",
            }

    # 2. Check Plan or Existing Quota
    total_amount = 0
    items = []
    metadata = {
        "listing_id": payload.listing_id,
        "ad_plan_id": payload.ad_plan_id
    }

    if getattr(payload, 'use_existing_quota', False):
        from routes.subscriptions import check_listing_quota
        user_stores = db.select("stores", filters={"user_id": user_id, "status": "active"})
        is_store_user = len(user_stores) > 0
        
        quota_info = await check_listing_quota(user_id, is_store_user)
        if not quota_info.get("has_active_subscription"):
            raise HTTPException(status_code=400, detail="No active subscription found.")
        if not quota_info.get("can_create"):
            raise HTTPException(status_code=400, detail="Your subscription quota is exhausted.")
        
        metadata["use_existing_quota"] = True
        items.append({
            "name": "Listing from Active Subscription",
            "amount": 0
        })
        
    else:
        if not payload.listing_plan_id:
            logger.warning(f"Checkout failed: no listing_plan_id provided by user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A subscription plan is required to list. Please select a plan or use existing quota."
            )

        plan = db.select_one("pricing_plans", payload.listing_plan_id)
        if not plan:
            logger.warning(f"Checkout failed: plan '{payload.listing_plan_id}' not found")
            raise HTTPException(status_code=404, detail="Listing plan not found")

        if not plan.get("is_active"):
            logger.warning(f"Checkout failed: plan '{payload.listing_plan_id}' is inactive")
            raise HTTPException(status_code=400, detail="This plan is no longer available")

        plan_price = plan.get("price", 0)
        if plan_price <= 0:
            logger.warning(f"Checkout rejected: plan '{plan['name_en']}' has price={plan_price} (free plans not allowed)")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Free listing plans are no longer available. Please select a paid plan."
            )

        total_amount += plan_price
        metadata["listing_plan_id"] = payload.listing_plan_id
        items.append({
            "name": f"Listing Plan: {plan['name_en']}",
            "amount": int(round(plan_price * 1000))
        })

    # 3. Calculate Ad Price (optional add-on)
    if payload.ad_plan_id:
        try:
            uuid.UUID(str(payload.ad_plan_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid ad_plan_id format")

        ad_plan = db.select_one("pricing_plans", payload.ad_plan_id)
        if not ad_plan:
            logger.warning(f"Checkout failed: ad plan '{payload.ad_plan_id}' not found")
            raise HTTPException(status_code=404, detail="Ad plan not found")

        ad_price = ad_plan.get("price", 0)
        plan_base_duration = ad_plan.get("duration_days", 1) or 1
        ad_duration = payload.ad_duration_days if payload.ad_duration_days and payload.ad_duration_days > 0 else plan_base_duration
        
        # Calculation: (requested days / plan base days) * plan price
        # Example: (10 days / 5 days) * 3 Riyal = 6 Riyal
        ad_total = (ad_duration / plan_base_duration) * ad_price
        
        if ad_total > 0:
            total_amount += ad_total
            items.append({
                "name": f"Ad Boost: {ad_plan['name_en']} ({ad_duration} days)",
                "amount": int(round(ad_total * 1000))
            })
            
        metadata["ad_duration_days"] = ad_duration

    # Add 2% processing fee
    if total_amount > 0:
        processing_fee = round(total_amount * 0.02, 3)
        total_amount += processing_fee
        items.append({
            "name": "Service Charge (2%)",
            "amount": int(round(processing_fee * 1000))
        })

    logger.info(f"Checkout total: {total_amount} {payload.currency} for {len(items)} items")
    
    if total_amount == 0:
        # Fast-track activation (bypassing Paymob)
        transaction_uuid = str(uuid.uuid4())
        payment_data = {
            "id": transaction_uuid,
            "user_id": user_id,
            "plan_id": payload.listing_plan_id if getattr(payload, 'listing_plan_id', None) else None,
            "amount": 0,
            "currency": payload.currency,
            "status": "success",
            "payment_method": "subscription_quota",
            "metadata": json.dumps(metadata)
        }
        db.insert("payments", payment_data)
        
        # Directly call the logic in activate_bundle
        await activate_bundle(transaction_uuid, metadata, user_id)
        
        return {
            "status": "success",
            "transaction_id": transaction_uuid,
            "payment_url": None,
            "message": "Listing submitted successfully using your active subscription."
        }

    # 4. Create Transaction Record
    transaction_uuid = str(uuid.uuid4())
    payment_data = {
        "id": transaction_uuid,
        "user_id": user_id,
        "plan_id": payload.listing_plan_id,
        "amount": total_amount,
        "currency": payload.currency,
        "status": "pending",
        "payment_method": "card",
        "metadata": json.dumps(metadata)
    }

    payment = db.insert("payments", payment_data)
    if not payment:
        logger.error(f"Failed to create payment record for user {user_id}")
        raise HTTPException(status_code=500, detail="Failed to create payment record")

    # 5. Initiate Payment (all listings are paid now)
    try:
        amount_cents = int(round(total_amount * 1000)) # OMR 3 decimals
        
        # Prepare Billing Data
        billing = {
            "email": current_user.get("email", "unknown@example.com"),
            "first_name": current_user.get("name", "User").split(" ")[0],
            "last_name": "Customer", 
            "phone_number": current_user.get("phone_number", "+96800000000")
        }
        
        # Create Intention
        payment_url = paymob.create_intention(
            amount_cents=amount_cents,
            currency=payload.currency,
            merchant_order_id=transaction_uuid,
            billing_data=billing,
            items=items
        )
        
        return {
            "status": "payment_initiated",
            "transaction_id": transaction_uuid,
            "payment_url": payment_url
        }
        
    except Exception as e:
        print(f"Checkout Error: {str(e)}")
        db.update("payments", transaction_uuid, {"status": "failed"})
        raise HTTPException(status_code=500, detail="Payment Gateway Error")


@router.post("/webhook")
async def payment_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Paymob Webhook — called by Paymob after payment is processed.
    Updates payment status. Listing activation is handled by Admin.
    """
    try:
        data = await request.json()
        obj = data.get("obj", {})
        merchant_order_id = obj.get("order", {}).get("merchant_order_id")
        success = obj.get("success", False)
        
        if not merchant_order_id:
            return {"status": "ignored", "reason": "no merchant_order_id"}
        
        # Verify Payment exists
        payment = db.select_one("payments", merchant_order_id)
        if not payment:
            return {"status": "not_found"}

        if payment["status"] == "success":
            return {"status": "already_processed"}
            
        status_update = "success" if success else "failed"
        
        # Update payment record
        db.update("payments", merchant_order_id, {
            "status": status_update,
            "paymob_transaction_id": str(obj.get("id", "")),
            "payment_method": obj.get("source_data", {}).get("sub_type", "card")
        })
        
        if success:
            # Activate listing and/or ads
            metadata = payment.get("metadata", {})
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            
            await activate_bundle(merchant_order_id, metadata, payment["user_id"])
            
        return {"status": "received"}
        
    except Exception as e:
        print(f"Webhook Error: {str(e)}")
        return {"status": "error", "detail": str(e)}

@router.post("/initiate")
async def deprecated_initiate():
    raise HTTPException(status_code=410, detail="Use /checkout endpoint instead")


@router.get("/payment-check")
async def payment_check(
    transaction_id: str = Query(..., description="The transaction_id returned from /checkout"),
    current_user: dict = Depends(get_current_customer)
):
    """
    Frontend polls this to check if payment was successful.
    Returns current payment status.
    """
    payment = db.select_one("payments", transaction_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    # Security: only the owner can check their payment
    if payment.get("user_id") != current_user.get("id"):
        raise HTTPException(status_code=403, detail="Access denied")
    
    metadata = payment.get("metadata", {})
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    
    return {
        "transaction_id": transaction_id,
        "status": payment.get("status"),       # pending | success | failed | cancelled
        "amount": payment.get("amount"),
        "currency": payment.get("currency"),
        "listing_id": metadata.get("listing_id"),
        "created_at": str(payment.get("created_at", ""))
    }


@router.get("/payment-success")
async def payment_success(
    transaction_id: str = Query(...),
    current_user: dict = Depends(get_current_customer)
):
    """
    Thank You page endpoint — called after Paymob redirects user back.
    Returns payment details to show the success message.
    """
    payment = db.select_one("payments", transaction_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    metadata = payment.get("metadata", {})
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    
    return {
        "status": "success",
        "transaction_id": transaction_id,
        "amount": payment.get("amount"),
        "currency": payment.get("currency"),
        "listing_id": metadata.get("listing_id"),
        "message": "Payment successful! Your listing is under review by our team."
    }


@router.get("/payment-cancel")
async def payment_cancel(
    transaction_id: str = Query(...),
    current_user: dict = Depends(get_current_customer)
):
    """
    Called when user cancels payment on Paymob checkout page.
    Updates payment status to cancelled.
    """
    payment = db.select_one("payments", transaction_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    # Only cancel if still pending
    if payment.get("status") == "pending":
        db.update("payments", transaction_id, {"status": "cancelled"})
    
    return {
        "status": "cancelled",
        "transaction_id": transaction_id,
        "message": "Payment was cancelled. Your listing was not submitted."
    }

@router.get("/my-transactions", response_model=schemas.TransactionListResponse)
async def my_transactions(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_customer)
):
    """
    Get all transactions for the current user.
    """
    def query_func(table):
        return table.select("*", count="exact").eq("user_id", current_user["id"]).order("created_at", desc=True).range(skip, skip + limit - 1)
        
    result = db.query("payments", query_func)
    
    transactions = result.data if result.data else []
    
    for t in transactions:
        meta = t.get("metadata", {})
        if isinstance(meta, str):
            try:
                t["metadata"] = json.loads(meta)
            except:
                t["metadata"] = {}
                
    total = result.count if result.count is not None else len(transactions)
    pages = math.ceil(total / limit) if total > 0 else 0
    page = (skip // limit) + 1 if limit > 0 else 1
    
    return {
        "transactions": transactions,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages
    }

# -------------------------------------------------
# ADMIN ENDPOINTS
# -------------------------------------------------

@admin_router.get("/transactions", response_model=schemas.AdminTransactionListResponse)
async def list_all_transactions_admin(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status: success, pending, failed, cancelled"),
    search: Optional[str] = Query(None, description="Search by transaction ID or paymob ID")
):
    """
    Admin: List all transactions with pagination and optional filters.
    """
    def query_func(table):
        query = table.select("*", count="exact")
        
        if status:
            query = query.eq("status", status)
        
        if search:
            query = query.or_(f"id.ilike.%{search}%,paymob_transaction_id.ilike.%{search}%")
            
        return query.order("created_at", desc=True).range(skip, skip + limit - 1)
        
    result = db.query("payments", query_func)
    transactions = result.data if result.data else []
    
    # Batch fetch user names
    user_names_map = {}
    if transactions:
        user_ids = list({t["user_id"] for t in transactions if t.get("user_id")})
        if user_ids:
            users_res = db.select_in("app_users", "id", user_ids)
            user_names_map = {u["id"]: u.get("name") for u in users_res} if users_res else {}
            
        for t in transactions:
            t["user_name"] = user_names_map.get(t.get("user_id"))

    total = result.count if result.count is not None else len(transactions)
    pages = math.ceil(total / limit) if total > 0 else 0
    page = (skip // limit) + 1 if limit > 0 else 1
    
    return {
        "transactions": transactions,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages
    }


@admin_router.get("/transactions/{transaction_id}", response_model=schemas.AdminTransactionDetail)
async def get_transaction_detail_admin(transaction_id: str):
    """
    Admin: Get full details of a specific transaction.
    """
    transaction = db.select_one("payments", transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    meta = transaction.get("metadata", {})
    if isinstance(meta, str):
        try:
            transaction["metadata"] = json.loads(meta)
        except:
            transaction["metadata"] = {}
            
    if transaction.get("user_id"):
        user = db.select_one("app_users", transaction["user_id"])
        if user:
            transaction["user_name"] = user.get("name")
            transaction["user_email"] = user.get("email")
            transaction["user_phone"] = user.get("phone_number")
            
    return transaction
