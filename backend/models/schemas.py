"""
Pydantic models for request/response validation
Models will be created module by module as needed
"""
from pydantic import BaseModel, EmailStr, constr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class UserCreate(BaseModel):
	name: str
	email: EmailStr
	# bcrypt has a 72 byte maximum; enforce a limit to avoid runtime errors
	password: constr(min_length=8, max_length=72)


class UserOut(BaseModel):
	id: str
	name: str
	email: EmailStr


class Token(BaseModel):
	access_token: str
	token_type: str


class LoginRequest(BaseModel):
	email: EmailStr
	password: constr(min_length=1, max_length=1024)


class ChangePasswordRequest(BaseModel):
	email: EmailStr
	# enforce bcrypt 72-byte max for new passwords as well
	new_password: constr(min_length=8, max_length=72)


# Category schemas
class CategoryCreate(BaseModel):
	name: str
	image_url: Optional[str] = None
	parent_id: Optional[str] = None
	attributes_schema: Optional[list | dict] = None
	is_active: bool = True


class CategoryUpdate(BaseModel):
	name: Optional[str] = None
	image_url: Optional[str] = None
	parent_id: Optional[str] = None
	attributes_schema: Optional[list | dict] = None
	is_active: Optional[bool] = None


class CategoryOut(BaseModel):
	id: str
	name_en: str
	name_ar: str
	image_url: Optional[str] = None
	parent_id: Optional[str] = None
	attributes_schema: Optional[list | dict] = None
	is_active: bool
	created_at: Optional[str] = None
	updated_at: Optional[str] = None


# Customer Auth schemas
class OTPRequest(BaseModel):
	phone_number: str


class OTPVerify(BaseModel):
	phone_number: str
	otp: str


class CustomerUpdate(BaseModel):
	name: str


class CustomerOut(BaseModel):
	id: str
	name: Optional[str] = None
	phone_number: str
	is_active: bool
	access_token: Optional[str] = None
	token_type: Optional[str] = None


# ----------------------------------------------------------------
# NEW MODELS - Pricing, Stores, Listings
# ----------------------------------------------------------------

# Pricing Plans
class PricingPlanCreate(BaseModel):
    name_en: str
    name_ar: str
    type: str # listing, store, banner
    price: float
    duration_days: int
    features: Optional[dict] = {}
    is_active: bool = True

class PricingPlanOut(PricingPlanCreate):
    id: str
    created_at: Optional[str] = None

# Stores
class StoreCreate(BaseModel):
    name: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    plan_id: Optional[str] = None # Optional for initial creation if logic handles free tier

class StoreUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    status: Optional[str] = None

class StoreOut(BaseModel):
    id: str
    user_id: str
    name: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    status: str
    plan_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[str] = None

# Listings
class ListingCreate(BaseModel):
    category_id: str
    store_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    price: float
    currency: str = "AED"
    plan_id: Optional[str] = None
    attributes_values: Optional[dict] = {}
    location: Optional[dict] = None
    images: Optional[List[str]] = [] # URLs

class ListingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    attributes_values: Optional[dict] = None
    location: Optional[dict] = None
    status: Optional[str] = None
    
class ListingOut(BaseModel):
    id: str
    user_id: str
    store_id: Optional[str] = None
    category_id: str
    title: str
    description: Optional[str] = None
    price: float
    currency: str
    status: str
    rejection_reason: Optional[str] = None
    attributes_values: Optional[dict] = None
    location: Optional[dict] = None
    created_at: Optional[str] = None
    # We might fetch images separately or include them here
