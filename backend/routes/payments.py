from fastapi import APIRouter, HTTPException, Depends, status, Request, BackgroundTasks, Query
from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from db.supabase_client import db
from utils.auth import get_current_customer
from utils.paymob import PaymobManager
from utils.logger import get_logger
from config.settings import settings
import uuid
import json
from datetime import datetime, timedelta

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/payments",
    tags=["payments"]
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
    try:
        logger.info(f"Activating bundle for payment={payment_id}, user={user_id}")

        listing_id = metadata.get("listing_id")
        listing_plan_id = metadata.get("listing_plan_id")
        ad_plan_id = metadata.get("ad_plan_id")

        # 1. Activate Listing — move to pending_approval and set expiration
        if listing_id:
            listing_expires_at = None

            # a) Create new subscription from the purchased plan
            if listing_plan_id:
                plan = db.select_one("pricing_plans", listing_plan_id)
                if plan:
                    days = plan.get("duration_days", 30)
                    quota = plan.get("quota", 0)

                    end_date = (datetime.utcnow() + timedelta(days=days)).isoformat()
                    listing_expires_at = end_date

                    sub_data = {
                        "user_id": user_id,
                        "plan_id": listing_plan_id,
                        "start_date": datetime.utcnow().isoformat(),
                        "end_date": end_date,
                        "remaining_quota": quota - 1 if quota > 0 else (quota if quota == -1 else 0),
                        "status": "active"
                    }
                    db.insert("user_subscriptions", sub_data)
                    logger.info(f"Subscription created: plan={listing_plan_id}, quota_remaining={sub_data['remaining_quota']}")

            # b) Or deduct from existing subscription
            elif metadata.get("use_existing_quota"):
                now = datetime.utcnow()
                def sub_query(table):
                    return table.select("*")\
                        .eq("user_id", user_id)\
                        .eq("status", "active")\
                        .gte("end_date", now.isoformat())\
                        .order("end_date", desc=True)\
                        .limit(1)
                sub_result = db.query("user_subscriptions", sub_query)
                active_sub = sub_result.data[0] if sub_result.data else None
                
                if active_sub:
                    remaining = active_sub.get("remaining_quota", 0)
                    if remaining > 0:
                        db.update("user_subscriptions", active_sub["id"], {"remaining_quota": remaining - 1})
                        logger.info(f"Deducted quota from subscription {active_sub['id']}. New remaining={remaining - 1}")
                    
                    listing_expires_at = active_sub.get("end_date")

            # Move listing to pending_approval and set expires_at
            listing_update = {"status": "pending_approval"}
            if listing_expires_at:
                listing_update["expires_at"] = listing_expires_at
                
            db.update("listings", listing_id, listing_update)
            logger.info(f"Listing {listing_id} moved to pending_approval (expires_at={listing_expires_at})")

        # 2. Activate Ad Boost
        if ad_plan_id:
            ad_duration_days = metadata.get("ad_duration_days", 1)
            ad_end_date = (datetime.utcnow() + timedelta(days=ad_duration_days)).isoformat()
            promo_data = {
                "listing_id": listing_id,
                "plan_id": ad_plan_id,
                "start_date": datetime.utcnow().isoformat(),
                "end_date": ad_end_date,
                "status": "active"
            }
            db.insert("listing_promotions", promo_data)
            logger.info(f"Ad boost {ad_plan_id} activated for listing {listing_id} for {ad_duration_days} days")

        # Update payment status
        db.update("payments", payment_id, {"status": "success"})
        logger.info(f"Payment {payment_id} marked as success")

    except Exception as e:
        logger.error(f"Bundle activation error for payment {payment_id}: {type(e).__name__}: {e}", exc_info=True)
        db.update("payments", payment_id, {"status": "failed_activation"})


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
        items.append("Listing from Active Subscription")
        
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
        items.append(f"Listing Plan: {plan['name_en']}")

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
        ad_duration = payload.ad_duration_days if payload.ad_duration_days and payload.ad_duration_days > 0 else 1
        ad_total = ad_price * ad_duration
        
        if ad_total > 0:
            total_amount += ad_total
            items.append(f"Ad Boost: {ad_plan['name_en']} ({ad_duration} days)")
            
        metadata["ad_duration_days"] = ad_duration

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
        amount_cents = int(total_amount * 1000) # OMR 3 decimals
        
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
