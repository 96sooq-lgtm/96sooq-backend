from fastapi import APIRouter, HTTPException, status, Query
from models import schemas
from db.supabase_client import db
from passlib.hash import bcrypt

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"]
)


@router.post("/signup", response_model=schemas.UserOut)
async def admin_signup(payload: schemas.UserCreate):
    # Check if user exists
    existing = db.select("users", filters={"email": payload.email})
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    # Validate password byte length for bcrypt (max 72 bytes)
    pwd_bytes = payload.password.encode("utf-8")
    if len(pwd_bytes) > 72:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Password is too long (max 72 bytes). Use a shorter password.")

    # Hash password and insert
    pwd_hash = bcrypt.hash(payload.password)
    created = db.insert("users", {
        "name": payload.name,
        "email": payload.email,
        "password_hash": pwd_hash
    })

    if not created:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create user")

    return {"id": created.get("id"), "name": created.get("name"), "email": created.get("email")}


@router.post("/login")
async def admin_login(payload: schemas.LoginRequest):
    users = db.select("users", filters={"email": payload.email})
    if not users:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user = users[0]
    stored_hash = user.get("password_hash")
    # For login, if provided password is longer than bcrypt limit, reject
    if len(payload.password.encode("utf-8")) > 72:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Password is too long (max 72 bytes).")

    if not stored_hash or not bcrypt.verify(payload.password, stored_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    return {"message": "Login successful", "user": {"id": user.get("id"), "name": user.get("name"), "email": user.get("email")}}


@router.post("/change-password")
async def change_password(payload: schemas.ChangePasswordRequest):
    users = db.select("users", filters={"email": payload.email})
    if not users:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user = users[0]
    # Validate new password length
    if len(payload.new_password.encode("utf-8")) > 72:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="New password is too long (max 72 bytes).")

    new_hash = bcrypt.hash(payload.new_password)
    updated = db.update("users", user.get("id"), {"password_hash": new_hash})
    if not updated:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update password")

    return {"message": "Password updated"}

# ============ USER MANAGEMENT ============

@router.get("/users", response_model=list[schemas.UserOut])
async def list_all_users(skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500)):
    """List all users (admin only) - with pagination"""
    def query_func(table):
        return table.select("id, name, email").range(skip, skip + limit - 1)
    
    result = db.query("users", query_func)
    
    if not result:
        return []
    
    return [
        {
            "id": user.get("id"),
            "name": user.get("name"),
            "email": user.get("email")
        }
        for user in result
    ]


@router.get("/users/{user_id}", response_model=schemas.UserOut)
async def get_user(user_id: str):
    """Get a specific user by ID (admin only)"""
    user = db.select_one("users", user_id, columns="id, name, email")
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {
        "id": user.get("id"),
        "name": user.get("name"),
        "email": user.get("email")
    }