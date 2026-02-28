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
    ad_plan_id: Optional[str] = None
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
    Metadata contains: listing_id, listing_plan_id, ad_plan_id.
    """
    try:
        print(f"Activating bundle for Payment: {payment_id}")
        
        listing_id = metadata.get("listing_id")
        listing_plan_id = metadata.get("listing_plan_id")
        ad_plan_id = metadata.get("ad_plan_id")
        
        # 1. Activate Listing (Plan or Quota)
        if listing_id:
            # Move listing to pending_approval
            db.update("listings", listing_id, {"status": "pending_approval"})
            print(f"Listing {listing_id} moved to pending_approval")
            
            # Use Plan logic if plan provided
            if listing_plan_id:
                plan = db.select_one("pricing_plans", listing_plan_id)
                if plan:
                     # If it's a paid plan, we might need to add quota?
                     # OR does this payment cover THIS listing only?
                     # User said: "basic (1 free)... other plans with number listings".
                     # If they buy a plan, they get quota. One quota is used for THIS listing.
                     
                     days = plan.get("duration_days", 30)
                     quota = plan.get("quota", 0)
                     
                     # Create Subscription
                     sub_data = {
                        "user_id": user_id,
                        "plan_id": listing_plan_id,
                        "start_date": datetime.utcnow().isoformat(),
                        "end_date": (datetime.utcnow() + timedelta(days=days)).isoformat(),
                        "remaining_quota": quota - 1 if quota > 0 else quota, # Consumes 1 for current listing
                        "status": "active"
                    }
                     db.insert("user_subscriptions", sub_data)
                     print(f"Subscription created for Plan {listing_plan_id}")

        # 2. Activate Ad Boost
        if ad_plan_id:
             # Create Ad Record (Promoted Listing?)
             # Assuming 'promoted_listings' table or similar logic exists?
             # Or just update listing with 'is_featured' / 'ad_expiry'?
             # Current schema doesn't describe Ad implementation details fully.
             # MVP: Log it. Real implementation would insert into `ads` table.
             print(f"Ad Boost {ad_plan_id} activated for Listing {listing_id}")
             # db.insert("promoted_listings", ...)
             
        # Update Payment Check
        db.update("payments", payment_id, {"status": "success"})

    except Exception as e:
        print(f"Activation Bundle Error: {str(e)}")
        # db.update("payments", payment_id, {"status": "failed_activation"})


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    payload: CheckoutItem,
    current_user: dict = Depends(get_current_customer)
):
    """
    Unified Checkout for Listing + Ads.
    Handles Free (Quota) and Paid flows.
    """
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
        
    try:
        if payload.listing_plan_id and len(payload.listing_plan_id) < 10:
             # Basic check to avoid short strings/placeholders
             pass
    except:
        pass

    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user token")
    
    # 1. Validate Listing
    listing = db.select_one("listings", payload.listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    total_amount = 0.0
    items = []
    metadata = {
        "listing_id": payload.listing_id,
        "listing_plan_id": payload.listing_plan_id,
        "ad_plan_id": payload.ad_plan_id
    }
    
    # 2. Calculate Listing Price
    if payload.listing_plan_id:
        plan = db.select_one("pricing_plans", payload.listing_plan_id)
        if not plan:
             raise HTTPException(status_code=404, detail="Listing Plan not found")
             
        price = plan.get("price")
        if price is None:
             price = 0.0
        total_amount += price
        items.append(f"Listing Plan: {plan['name_en']}")
        
        # Validation: If Free Plan, check if user already used it?
        # TODO: Strict "Free Logic" check here if price == 0.
        
    # 3. Calculate Ad Price
    if payload.ad_plan_id:
        # Validate UUID format to prevent 500 errors from DB
        try:
            uuid.UUID(str(payload.ad_plan_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid ad_plan_id format")

        ad_plan = db.select_one("pricing_plans", payload.ad_plan_id)
        if not ad_plan:
             raise HTTPException(status_code=404, detail="Ad Plan not found")
             
        price = ad_plan.get("price")
        if price is None:
             price = 0.0
        total_amount += price
        items.append(f"Ad: {ad_plan['name_en']}")

    # 4. Create Transaction Record
    transaction_uuid = str(uuid.uuid4())
    payment_data = {
        "id": transaction_uuid,
        "user_id": user_id,
        "plan_id": payload.listing_plan_id, # Primary plan? 
        # schema requires plan_id not null... let's use listing plan or ad plan or check schema
        # Schema: plan_id NOT NULL. We might need a dummy ID or relaxed constraint if paying for ad ONLY?
        # Let's assume listing_plan_id is always present for now.
        "amount": total_amount,
        "currency": payload.currency,
        "status": "pending",
        "payment_method": "system" if total_amount == 0 else "card",
        "metadata": json.dumps(metadata)
    }
    
    # Check plan_id constraint
    if not payload.listing_plan_id:
         # If paying for Ad only on existing listing?
         # For this specific flow (New Listing), listing_plan_id is expected.
         if payload.ad_plan_id:
             payment_data["plan_id"] = payload.ad_plan_id
         else:
             # Should not happen if strictly following flow
             # Using a fallback or error
             pass

    payment = db.insert("payments", payment_data)
    
    # 5. Handle Free/Quota Flow
    if total_amount == 0:
        # Immediate Activation
        await activate_bundle(transaction_uuid, metadata, user_id)
        return {
            "status": "success",
            "transaction_id": transaction_uuid,
            "message": "Order processed successfully. Listing is under review."
        }
        
    # 6. Handle Paid Flow
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
            # Move listing to 'pending_approval' — Admin will review and activate
            metadata = payment.get("metadata", {})
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            
            listing_id = metadata.get("listing_id")
            listing_plan_id = metadata.get("listing_plan_id")
            user_id = payment["user_id"]
            
            if listing_id:
                db.update("listings", listing_id, {"status": "pending_approval"})
                print(f"Listing {listing_id} moved to pending_approval (awaiting admin review)")
            
            # Create subscription record if a plan was purchased
            if listing_plan_id:
                plan = db.select_one("pricing_plans", listing_plan_id)
                if plan:
                    days = plan.get("duration_days", 30)
                    quota = plan.get("quota", 0)
                    sub_data = {
                        "user_id": user_id,
                        "plan_id": listing_plan_id,
                        "start_date": datetime.utcnow().isoformat(),
                        "end_date": (datetime.utcnow() + timedelta(days=days)).isoformat(),
                        "remaining_quota": quota - 1 if quota > 0 else quota,
                        "status": "active"
                    }
                    db.insert("user_subscriptions", sub_data)
                    print(f"Subscription created for Plan {listing_plan_id}")
            
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
