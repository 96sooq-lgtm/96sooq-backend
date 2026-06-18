from fastapi import APIRouter, HTTPException, status, Depends, Request
from models import schemas
from db.supabase_client import db
from utils.auth import create_access_token, create_customer_token, get_current_customer
from utils.logger import get_logger
from pydantic import BaseModel, EmailStr
from typing import Optional
try:
    from main import limiter
except ImportError:
    limiter = None

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"]
)



# -------------------------------------------------
# OAUTH MODELS
# -------------------------------------------------
class OAuthCheckRequest(BaseModel):
    provider: str  # 'google', 'apple', 'facebook'
    provider_id: str
    email: EmailStr

class OAuthCheckResponse(BaseModel):
    exists: bool
    email: Optional[str] = None
    access_token: Optional[str] = None
    token_type: Optional[str] = None
    user: Optional[dict] = None

class OAuthCompleteProfileRequest(BaseModel):
    provider: str
    provider_id: str
    email: EmailStr
    name: str
    phone_number: str
    profile_picture: Optional[str] = None

# -------------------------------------------------
# OAUTH ENDPOINTS (TWO-STEP FLOW)
# -------------------------------------------------

@router.post("/oauth/check-user", response_model=OAuthCheckResponse)
def oauth_check_user(request: Request, payload: OAuthCheckRequest):
    """
    Step 1: Check if user exists after Google/Apple/Facebook OAuth.
    
    Flow:
    1. Frontend handles Google OAuth (gets provider_id, email)
    2. Frontend calls this endpoint to check if user exists
    3. If exists → return JWT token (user is logged in)
    4. If new → return exists: false (frontend should ask for name & phone)
    """
    provider = payload.provider.lower()
    
    # Validate provider
    valid_providers = ['google', 'apple', 'facebook']
    if provider not in valid_providers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider. Must be one of: {valid_providers}"
        )
    
    # Check if user exists (by provider + provider_id)
    existing = db.select("app_users", filters={
        "provider": provider,
        "provider_id": payload.provider_id
    })
    
    if existing:
        # User exists - return JWT token
        user = existing[0]
        
        # Check if user is active
        if not user.get("is_active", True):
            # Distinguish: self-deleted (has deleted_at) vs admin-blocked (no deleted_at)
            if user.get("deleted_at"):
                # User previously deleted their own account — reactivate on re-login
                # (Apple App Store Guideline 5.1.1: deleted users must be able to re-register)
                db.update("app_users", user["id"], {"is_active": True, "deleted_at": None})
                user["is_active"] = True
                logger.info(f"Reactivated self-deleted user {user['id']} via {provider}")
            else:
                # Admin-blocked user — do NOT reactivate
                raise HTTPException(status_code=403, detail="Account is locked or deactivated")
            
        access_token = create_customer_token(data={
            "sub": user.get("email") or user.get("provider_id"),
            "role": "customer",
            "user_id": user["id"]
        })
        
        return {
            "exists": True,
            "email": user.get("email"),
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user["id"],
                "name": user.get("name"),
                "email": user.get("email"),
                "phone_number": user.get("phone_number"),
                "profile_picture": user.get("profile_picture")
            }
        }
    else:
        # User does NOT exist - needs profile completion
        return {
            "exists": False,
            "email": payload.email
        }


@router.post("/oauth/complete-profile", response_model=schemas.CustomerOut)
def oauth_complete_profile(payload: OAuthCompleteProfileRequest):
    """
    Step 2: Complete user profile for new OAuth users.
    
    Flow:
    1. Frontend received exists: false from check-user
    2. Frontend shows form asking for: Name, Phone Number
    3. User fills form and submits
    4. Backend creates user with all data
    5. Returns JWT token
    """
    provider = payload.provider.lower()
    
    # Validate provider
    valid_providers = ['google', 'apple', 'facebook']
    if provider not in valid_providers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider. Must be one of: {valid_providers}"
        )
    
    # Double-check user doesn't already exist
    existing = db.select("app_users", filters={
        "provider": provider,
        "provider_id": payload.provider_id
    })
    
    if existing:
        user = existing[0]
        # If the existing record is a self-deleted account, reactivate with new profile data
        if not user.get("is_active", True) and user.get("deleted_at"):
            updated = db.update("app_users", user["id"], {
                "is_active": True,
                "deleted_at": None,
                "name": payload.name,
                "phone_number": payload.phone_number,
                "email": payload.email,
                "profile_picture": payload.profile_picture,
            })
            if not updated:
                raise HTTPException(status_code=500, detail="Failed to reactivate account")
            
            logger.info(f"Reactivated self-deleted user {user['id']} via complete-profile")
            
            access_token = create_customer_token(data={
                "sub": payload.email,
                "role": "customer",
                "user_id": user["id"]
            })
            return {
                "id": user["id"],
                "name": payload.name,
                "phone_number": payload.phone_number,
                "is_active": True,
                "access_token": access_token,
                "token_type": "bearer"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already exists. Please use check-user endpoint."
            )
    
    # Check if phone number is already taken (exclude deactivated/self-deleted accounts)
    existing_phone = db.select("app_users", filters={"phone_number": payload.phone_number})
    if existing_phone:
        # Only block if the existing record is an active account
        active_phone_users = [u for u in existing_phone if u.get("is_active", True)]
        if active_phone_users:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mobile number already exists"
            )

    # Check if email is already taken (exclude deactivated/self-deleted accounts)
    existing_email = db.select("app_users", filters={"email": payload.email})
    if existing_email:
        active_email_users = [u for u in existing_email if u.get("is_active", True)]
        if active_email_users:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )
    
    # Create new user
    new_user_data = {
        "provider": provider,
        "provider_id": payload.provider_id,
        "email": payload.email,
        "name": payload.name,
        "phone_number": payload.phone_number,
        "profile_picture": payload.profile_picture,
        "is_active": True
    }
    
    user = db.insert("app_users", new_user_data)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )
    
    # Generate JWT token
    access_token = create_customer_token(data={
        "sub": user["email"],
        "role": "customer",
        "user_id": user["id"]
    })
    
    return {
        "id": user["id"],
        "name": user.get("name"),
        "phone_number": user.get("phone_number"),
        "is_active": user["is_active"],
        "access_token": access_token,
        "token_type": "bearer"
    }


# -------------------------------------------------
# PHONE OTP ENDPOINTS (Legacy - keeping for backwards compatibility)
# -------------------------------------------------

