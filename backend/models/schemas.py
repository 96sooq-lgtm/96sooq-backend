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
    type: str # listing, ad, offer
    price: float
    duration_days: int
    quota: int = 0 # 0 means unlimited? Or use -1? Let's say 0 is valid for ad/offer without quantity limit? 
    # Actually, for listings: 1 free, 5 paid. For store: unlimited.
    # Let's say: quota is the number of listings allowed per month.
    # If -1, unlimited.
    target_audience: str = "individual" # individual, store
    description: Optional[str] = None
    features: Optional[dict] = {}
    is_active: bool = True

class PricingPlanOut(PricingPlanCreate):
    id: str
    created_at: Optional[str] = None

# Stores
class StoreCreate(BaseModel):
    name_en: str
    name_ar: str
    description: Optional[str] = None
    location_id: UUID # UUID for Governorate
    place_id: UUID # UUID for City (Wilayat)
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    plan_id: Optional[str] = None # Optional for creation (e.g. free trial or select later)

class StoreUpdate(BaseModel):
    name_en: Optional[str] = None
    name_ar: Optional[str] = None
    description: Optional[str] = None
    location_id: Optional[str] = None
    place_id: Optional[str] = None
    logo_url: Optional[str] = None
    cover_image_url: Optional[str] = None
    status: Optional[str] = None

class StoreOut(BaseModel):
    id: str
    user_id: str
    name: str # Retaining for backward compatibility or mapping
    name_ar: Optional[str] = None
    description: Optional[str] = None
    location_id: Optional[str] = None
    place: Optional[str] = None
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
class AdBannerCreate(BaseModel):
    user_id: str
    name: str # Auto-generated? Or user provided? Let's keep it.
    description: Optional[str] = None
    type: str # carousel, product_listing, top_offers, chat_screen
    image_url: Optional[str] = None # Optional if boosting a listing (use listing image)
    link_url: Optional[str] = None
    plan_id: Optional[str] = None
    listing_id: Optional[str] = None # Required for boosting
    plan_id: Optional[str] = None

class AdBannerUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    status: Optional[str] = None # pending_payment, pending_approval, active, rejected, expired

class AdBannerOut(BaseModel):
    id: str
    user_id: str
    name: str
    description: Optional[str] = None
    type: Optional[str] = None
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    status: str
    plan_id: Optional[str] = None
    listing_id: Optional[str] = None
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
