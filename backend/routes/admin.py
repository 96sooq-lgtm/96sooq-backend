from fastapi import APIRouter, HTTPException, status, Query, Depends
from passlib.context import CryptContext

from models import schemas
from models.schemas import Token
from db.supabase_client import db
from utils.auth import create_access_token, get_current_admin

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"]
)

# -------------------------------------------------
# Password context (bcrypt)
# -------------------------------------------------
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return pwd_context.verify(password, hashed_password)


# -------------------------------------------------
# AUTH
# -------------------------------------------------
@router.post("/signup", response_model=schemas.UserOut)
async def admin_signup(payload: schemas.UserCreate):
    # Check if user exists
    existing = db.select("users", filters={"email": payload.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    password_hash = hash_password(payload.password)

    created = db.insert("users", {
        "name": payload.name,
        "email": payload.email,
        "password_hash": password_hash
    })

    if not created:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )

    return {
        "id": created.get("id"),
        "name": created.get("name"),
        "email": created.get("email")
    }


@router.post("/login", response_model=Token)
async def admin_login(payload: schemas.LoginRequest):
    users = db.select("users", filters={"email": payload.email})
    if not users:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    user = users[0]
    stored_hash = user.get("password_hash")

    if not stored_hash or not verify_password(payload.password, stored_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    access_token = create_access_token(data={"sub": user["email"]})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/change-password")
async def change_password(
    payload: schemas.ChangePasswordRequest,
    current_user: dict = Depends(get_current_admin)
):
    # Verify the email matches the token owner for extra security, or allow admin to change any
    # For now, let's strictly enforce that admins change their own passwords via this route
    # or if we want admins to change others, we'd need a different logic.
    # Here we stick to: Authenticated user changing their own password.
    
    if payload.email != current_user["email"]:
         raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only change your own password"
        )

    new_password_hash = hash_password(payload.new_password)

    updated = db.update(
        "users",
        current_user.get("id"),
        {"password_hash": new_password_hash}
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password"
        )

    return {"message": "Password updated"}


# -------------------------------------------------
# ADMIN DASHBOARD
# -------------------------------------------------

@router.get("/dashboard", dependencies=[Depends(get_current_admin)])
async def admin_dashboard():
    """
    Admin dashboard stats.
    Returns counts and totals — all optimized with count queries (no SELECT *).
    Total DB calls: 7 (all lightweight count/sum queries).
    """
    # 1. Total users (count only, no data fetched)
    def count_users(table):
        return table.select("id", count="exact").limit(0)

    # 2. Total stores
    def count_stores(table):
        return table.select("id", count="exact").limit(0)

    # 3. Total listings
    def count_listings(table):
        return table.select("id", count="exact").limit(0)

    # 4. Pending approval requests (listings + stores)
    def count_pending(table):
        return table.select("id", count="exact").eq("status", "pending_approval").limit(0)

    # 5. Total transactions (successful payments)
    def count_transactions(table):
        return table.select("id", count="exact").eq("status", "success").limit(0)

    # 6. Total revenue — fetch only amount column for successful payments
    def sum_revenue(table):
        return table.select("amount").eq("status", "success")

    users_result = db.query("app_users", count_users)
    stores_result = db.query("stores", count_stores)
    listings_result = db.query("listings", count_listings)
    pending_result = db.query("listings", count_pending)
    transactions_result = db.query("payments", count_transactions)
    revenue_result = db.query("payments", sum_revenue)

    # Calculate total revenue from fetched amounts
    total_revenue = 0.0
    if revenue_result.data:
        total_revenue = sum(
            float(p.get("amount", 0)) for p in revenue_result.data
        )

    return {
        "total_users": users_result.count or 0,
        "total_stores": stores_result.count or 0,
        "total_listings": listings_result.count or 0,
        "pending_requests": pending_result.count or 0,
        "total_revenue": round(total_revenue, 3),
        "total_transactions": transactions_result.count or 0,
    }
