from fastapi import APIRouter, HTTPException, status, Depends
from models import schemas
from db.supabase_client import db
from utils.auth import create_access_token, get_current_customer
from pydantic import BaseModel, EmailStr
from typing import Optional

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"]
)

# Dummy OTP for now
DUMMY_OTP = "123456"

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
async def oauth_check_user(payload: OAuthCheckRequest):
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
        
        access_token = create_access_token(data={
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
async def oauth_complete_profile(payload: OAuthCompleteProfileRequest):
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists. Please use check-user endpoint."
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
    access_token = create_access_token(data={
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
@router.post("/send-otp")
async def send_otp(payload: schemas.OTPRequest):
    """
    Send OTP to the given phone number.
    If user doesn't exist, create a temporary record or update existing with new OTP.
    For MVP, we just set the OTP to '123456' in the database.
    """
    phone = payload.phone_number
    
    # Check if user exists
    existing = db.select("app_users", filters={"phone_number": phone})
    
    if existing:
        user_id = existing[0]["id"]
        # Update OTP
        updated = db.update("app_users", user_id, {"otp": DUMMY_OTP})
        if not updated:
            raise HTTPException(status_code=500, detail="Failed to generate OTP")
    else:
        # Create new user with null name
        new_user = db.insert("app_users", {
            "phone_number": phone,
            "otp": DUMMY_OTP,
            "provider": "phone"
            # name is null by default
            # is_active is true by default
        })
        if not new_user:
             raise HTTPException(status_code=500, detail="Failed to create user")

    return {"message": "OTP sent successfully"}


@router.post("/verify-otp", response_model=schemas.CustomerOut)
async def verify_otp(payload: schemas.OTPVerify):
    """
    Verify OTP. If valid, return JWT token and user info.
    """
    phone = payload.phone_number
    otp = payload.otp
    
    # Find user
    users = db.select("app_users", filters={"phone_number": phone})
    if not users:
        raise HTTPException(status_code=400, detail="Invalid phone number or OTP")
    
    user = users[0]
    
    # Check OTP
    # In production, check expiration too
    if user.get("otp") != otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
        
    # Clear OTP after successful verification (optional, but good practice)
    # db.update("app_users", user["id"], {"otp": None})
    
    # Generate Token
    access_token = create_access_token(data={"sub": phone, "role": "customer", "user_id": user["id"]})
    
    return {
        "id": user["id"],
        "name": user.get("name"),
        "phone_number": user["phone_number"],
        "is_active": user["is_active"],
        "access_token": access_token,
        "token_type": "bearer"
    }


@router.post("/create-user", response_model=schemas.CustomerOut)
async def create_user(
    payload: schemas.CustomerUpdate,
    current_user: dict = Depends(get_current_customer)
):
    """
    Complete user profile (update name).
    Requires authenticated user (customer).
    """
    updated = db.update(
        "app_users",
        current_user["id"],
        {"name": payload.name}
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update profile"
        )
        
    # Generate new token (refreshes session)
    access_token = create_access_token(data={"sub": updated.get("phone_number") or updated.get("email"), "role": "customer", "user_id": updated["id"]})

    return {
        "id": updated["id"],
        "name": updated.get("name"),
        "phone_number": updated.get("phone_number"),
        "is_active": updated["is_active"],
        "access_token": access_token,
        "token_type": "bearer"
    }
