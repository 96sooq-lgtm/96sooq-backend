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
	name_en: str
	name_ar: str
	image_url: Optional[str] = None
	parent_id: Optional[str] = None
	attributes_schema: Optional[list | dict] = None
	is_active: bool = True


class CategoryUpdate(BaseModel):
	name_en: Optional[str] = None
	name_ar: Optional[str] = None
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
	parent_name_en: Optional[str] = None
	parent_name_ar: Optional[str] = None
	attributes_schema: Optional[list | dict] = None
	is_active: bool
	created_at: Optional[str] = None
	updated_at: Optional[str] = None


# Customer Auth schemas
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
    type: str  # listing, ad, offer
    price: float
    duration_days: int
    quota: int = 0
    target_audience: str = "individual"  # individual, store
    description: Optional[str] = None
    features: Optional[dict] = {}
    is_active: bool = True
    is_best_value: bool = False

class PricingPlanUpdate(BaseModel):
    name_en: Optional[str] = None
    name_ar: Optional[str] = None
    type: Optional[str] = None
    price: Optional[float] = None
    duration_days: Optional[int] = None
    quota: Optional[int] = None
    target_audience: Optional[str] = None
    description: Optional[str] = None
    features: Optional[dict] = None
    is_active: Optional[bool] = None
    is_best_value: Optional[bool] = None

class PricingPlanOut(PricingPlanCreate):
    id: str
    created_at: Optional[str] = None


# Stores
class StoreListOut(BaseModel):
    id: str
    name: str
    name_ar: Optional[str] = None
    logo: Optional[str] = None


class StoreCreate(BaseModel):
    name_en: str
    name_ar: str
    description: Optional[str] = None
    governorate_id: UUID  # UUID for Governorate (State)
    wilayat_id: UUID      # UUID for Wilayat (City)
    logo: Optional[str] = None
    store_number: Optional[str] = None  # Omani phone number e.g. +96891234567
    plan_id: Optional[str] = None

class StoreUpdate(BaseModel):
    name_en: Optional[str] = None
    name_ar: Optional[str] = None
    description: Optional[str] = None
    governorate_id: Optional[str] = None
    wilayat_id: Optional[str] = None
    logo: Optional[str] = None
    store_number: Optional[str] = None
    status: Optional[str] = None

class StoreOut(BaseModel):
    id: str
    user_id: str
    name: str
    name_ar: Optional[str] = None
    description: Optional[str] = None
    governorate_id: Optional[str] = None
    wilayat: Optional[str] = None
    logo: Optional[str] = None
    store_number: Optional[str] = None
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
    condition: str # new, used
    price: float
    currency: str = "AED"
    location_id: str # UUID for Governorate
    place_id: str # UUID for City (Wilayat)
    plan_id: Optional[str] = None
    attributes_values: Optional[dict] = {}
    images: Optional[List[str]] = [] # URLs

class ListingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    condition: Optional[str] = None
    price: Optional[float] = None
    location_id: Optional[str] = None
    place_id: Optional[str] = None
    attributes_values: Optional[dict] = None
    status: Optional[str] = None
    
class ListingOut(BaseModel):
    id: str
    user_id: str
    store_id: Optional[str] = None
    category_id: str
    title: str
    description: Optional[str] = None
    condition: Optional[str] = None
    place: Optional[str] = None
    price: float
    currency: str
    status: str
    rejection_reason: Optional[str] = None
    attributes_values: Optional[dict] = None
    location_id: Optional[str] = None
    location_details: Optional[dict] = None # Populated with location name/type
    created_at: Optional[str] = None
# Ad Banners
# User boost: minimal payload — all other fields auto-derived from listing + JWT
class UserBoostCreate(BaseModel):
    listing_id: str
    type: str  # carousel, product_listing, top_offers, chat_screen
    plan_id: Optional[str] = None
    description: Optional[str] = None

# Admin banner: no user_id, no plan_id — admin creates system banners directly
class AdminBannerCreate(BaseModel):
    name: str
    type: str  # carousel, product_listing, top_offers, chat_screen
    duration_days: int = 30  # How long the banner stays active
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    description: Optional[str] = None

# Keep for backward-compat (used internally only)
class AdBannerCreate(BaseModel):
    user_id: str
    name: str
    description: Optional[str] = None
    type: str
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    plan_id: Optional[str] = None
    listing_id: Optional[str] = None


class AdBannerUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    duration_days: Optional[int] = None
    status: Optional[str] = None  # pending_approval, active, rejected, expired


class AdBannerOut(BaseModel):
    id: str
    user_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    type: Optional[str] = None
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    status: str
    plan_id: Optional[str] = None
    listing_id: Optional[str] = None
    duration_days: Optional[int] = None
    clicks: int = 0
    expires_at: Optional[datetime] = None
    created_at: Optional[str] = None


# ----------------------------------------------------------------
# SUBSCRIPTIONS (User Purchased)
# ----------------------------------------------------------------
class UserSubscriptionBase(BaseModel):
    plan_id: str

class UserSubscriptionCreate(UserSubscriptionBase):
    pass

class UserSubscriptionOut(UserSubscriptionBase):
    id: str
    user_id: str
    start_date: datetime
    end_date: datetime
    remaining_quota: int
    status: str
    plan_details: Optional[PricingPlanOut] = None

    class Config:
        orm_mode = True
