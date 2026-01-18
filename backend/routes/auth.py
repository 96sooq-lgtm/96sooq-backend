from fastapi import APIRouter, HTTPException, status, Depends
from models import schemas
from db.supabase_client import db
from utils.auth import create_access_token, get_current_customer

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"]
)

# Dummy OTP for now
DUMMY_OTP = "123456"

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
            "otp": DUMMY_OTP
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
    access_token = create_access_token(data={"sub": updated["phone_number"], "role": "customer", "user_id": updated["id"]})

    return {
        "id": updated["id"],
        "name": updated.get("name"),
        "phone_number": updated["phone_number"],
        "is_active": updated["is_active"],
        "access_token": access_token,
        "token_type": "bearer"
    }
