from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from config.settings import settings
from db.supabase_client import db
from models import schemas

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/admin/login", auto_error=False)

CUSTOMER_TOKEN_EXPIRE_DAYS = 90   # Mobile app — token valid until logout
ADMIN_TOKEN_EXPIRE_DAYS = 1       # Admin panel — short-lived for security

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=ADMIN_TOKEN_EXPIRE_DAYS)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt

def create_customer_token(data: dict) -> str:
    """Issues a 90-day JWT for mobile app users."""
    return create_access_token(data, expires_delta=timedelta(days=CUSTOMER_TOKEN_EXPIRE_DAYS))

async def get_current_admin(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = db.select("users", filters={"email": email})
    if not user:
        raise credentials_exception
        
    return user[0]


async def get_current_customer(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        sub: str = payload.get("sub")
        role: str = payload.get("role")
        
        if sub is None or role != "customer":
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
        
    # Check if sub is email or phone
    if "@" in sub:
        user = db.select("app_users", filters={"email": sub})
    else:
        user = db.select("app_users", filters={"phone_number": sub})
        
    if not user:
        raise credentials_exception
    
    # Block deactivated/deleted users from using old JWT tokens
    if not user[0].get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )
        
    return user[0]


def decode_customer_token(token: str) -> dict:
    """
    Decode and validate a customer JWT token string.
    Returns the app_user dict. Raises HTTPException on failure.
    Used for optional auth patterns where Depends() can't be used.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        sub: str = payload.get("sub")
        role: str = payload.get("role")
        if sub is None or role != "customer":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    if "@" in sub:
        user = db.select("app_users", filters={"email": sub})
    else:
        user = db.select("app_users", filters={"phone_number": sub})

    if not user:
        raise credentials_exception

    # Block deactivated/deleted users from using old JWT tokens
    if not user[0].get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )

    return user[0]

async def get_optional_current_customer(token: Optional[str] = Depends(oauth2_scheme_optional)):
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        sub: str = payload.get("sub")
        role: str = payload.get("role")
        if sub is None or role != "customer":
            return None
    except JWTError:
        return None

    if "@" in sub:
        user = db.select("app_users", filters={"email": sub})
    else:
        user = db.select("app_users", filters={"phone_number": sub})

    if not user:
        return None

    # Deactivated users get no auth context (silent rejection for optional auth)
    if not user[0].get("is_active", True):
        return None

    return user[0]
