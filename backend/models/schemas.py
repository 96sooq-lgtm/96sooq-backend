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
# Attribute definition for subcategory dynamic fields
class AttributeDefinition(BaseModel):
    name: str                           # field key, e.g. "fuel"
    label_en: str                       # English label shown in UI
    label_ar: Optional[str] = None      # Arabic label
    type: str                           # "radio" | "dropdown" | "text_field"
    options: Optional[List[str]] = []   # choices for radio/dropdown e.g. ["Petrol","Diesel"]
    required: bool = False
    status: str = "active"             # "active" | "inactive"


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


# App User Management for Admins
class AppUserAdminListItem(BaseModel):
    id: str
    name: str
    phone_number: str
    email: Optional[str] = None
    is_active: bool
    is_store: bool
    
class AppUserAdminDetail(BaseModel):
    id: str
    name: str
    phone_number: str
    email: Optional[str] = None
    is_active: bool
    provider: Optional[str] = None
    profile_picture: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    is_store: bool
    store_details: Optional[dict] = None
    stats: Optional[dict] = None  # Add user stats (total listings, transactions, etc)
    
class AppUserAdminListResponse(BaseModel):
    users: List[AppUserAdminListItem]
    total: int
    page: int
    limit: int
    pages: int


# ----------------------------------------------------------------
# NEW MODELS - Pricing, Stores, Listings
# ----------------------------------------------------------------

# Pricing Plans
class PricingPlanCreate(BaseModel):
    name_en: str
    name_ar: str
    type: str  # listing, ad, offer
    ad_sub_type: Optional[str] = None  # product_listing, chat_screen, offers (only when type='ad')
    price: float
    duration_days: int
    quota: int = 0
    target_audience: str = "individual"  # individual, store, everyone
    description: Optional[str] = None
    features: Optional[dict] = {}
    is_active: bool = True
    is_best_value: bool = False

class PricingPlanUpdate(BaseModel):
    name_en: Optional[str] = None
    name_ar: Optional[str] = None
    type: Optional[str] = None
    ad_sub_type: Optional[str] = None
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
    status: Optional[str] = None
    logo: Optional[str] = None
    average_rating: Optional[float] = 0.0
    total_reviews: Optional[int] = 0


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
    average_rating: Optional[float] = 0.0
    total_reviews: Optional[int] = 0
    is_own_store: Optional[bool] = False
    governorate_en: Optional[str] = None
    governorate_ar: Optional[str] = None
    wilayat_en: Optional[str] = None
    wilayat_ar: Optional[str] = None

# Store Reviews
class StoreReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None

class StoreReviewOut(BaseModel):
    id: str
    reviewer_id: str
    store_id: str
    rating: int
    comment: Optional[str] = None
    reviewer_name: Optional[str] = None
    created_at: Optional[str] = None

class StoreReviewsResponse(BaseModel):
    reviews: List[StoreReviewOut]
    average_rating: float
    total_reviews: int
    rating_breakdown: Dict[str, int]  # {"5": 488, "4": 74, "3": 14, "2": 0, "1": 0}
    page: int
    limit: int
    pages: int

class AdminStoreListItem(BaseModel):
    id: str
    name: str
    name_ar: Optional[str] = None
    status: str
    logo: Optional[str] = None

class AdminStoreListResponse(BaseModel):
    stores: List[AdminStoreListItem]
    total: int
    page: int
    limit: int
    pages: int

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
    images: Optional[List[str]] = None
    
class ListingOut(BaseModel):
    id: str
    user_id: str
    store_id: Optional[str] = None
    category_id: str
    title: str
    description: Optional[str] = None
    condition: Optional[str] = None
    place: Optional[str] = None # Legacy place name string
    price: float
    currency: str
    status: str
    rejection_reason: Optional[str] = None
    attributes_values: Optional[dict] = None
    location_id: Optional[str] = None
    location_name_en: Optional[str] = None
    location_name_ar: Optional[str] = None
    place_name_en: Optional[str] = None
    place_name_ar: Optional[str] = None
    created_at: Optional[str] = None
    seller_type: str = "individual"
    user_name: Optional[str] = None
    user_profile_picture: Optional[str] = None
    is_favorite: Optional[bool] = False
    seller_phone_number: Optional[str] = None
    store_name: Optional[str] = None
    store_logo: Optional[str] = None
    images: Optional[List[str]] = []
    promotions: Optional[List[dict]] = []
    is_promoted: bool = False

class FavoriteListingOut(ListingOut):
    favorited_at: Optional[str] = None

class FavoriteListResponse(BaseModel):
    listings: List[FavoriteListingOut]
    total: int
    page: int
    limit: int
    pages: int

# Ad Banners
# User boost: minimal payload — all other fields auto-derived from listing + JWT
class UserBoostCreate(BaseModel):
    listing_id: str
    type: str  # carousel, product_listing, top_offers, chat_screen
    plan_id: Optional[str] = None
    description: Optional[str] = None

class AdminBannerCreate(BaseModel):
    name: str
    type: str  # carousel, offers, product_listing, top_offers, chat_screen
    duration_days: int = 30
    image_url: Optional[str] = None   # single image (for carousel type)
    images: Optional[List[str]] = []  # multiple images (for offers type)
    link_url: Optional[str] = None
    whatsapp_number: Optional[str] = None
    description: Optional[str] = None

# Keep for backward-compat (used internally only)
class AdBannerCreate(BaseModel):
    user_id: str
    name: str
    description: Optional[str] = None
    type: str
    image_url: Optional[str] = None
    link_url: Optional[str] = None
    whatsapp_number: Optional[str] = None
    plan_id: Optional[str] = None
    listing_id: Optional[str] = None


class AdBannerUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    image_url: Optional[str] = None
    images: Optional[List[str]] = None
    link_url: Optional[str] = None
    whatsapp_number: Optional[str] = None
    duration_days: Optional[int] = None
    status: Optional[str] = None  # pending_approval, active, rejected, expired



class AdBannerOut(BaseModel):
    id: str
    user_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    type: Optional[str] = None
    image_url: Optional[str] = None
    images: Optional[List[str]] = []  # multi-image for offers type
    link_url: Optional[str] = None
    whatsapp_number: Optional[str] = None
    status: str
    plan_id: Optional[str] = None
    listing_id: Optional[str] = None
    duration_days: Optional[int] = None
    clicks: int = 0
    expires_at: Optional[datetime] = None
    created_at: Optional[str] = None
    creator_role: Optional[str] = "admin"  # "admin" or "user"
    
    # Enrichments
    is_admin_offer: Optional[bool] = None
    store_mobile_number: Optional[str] = None
    store_name: Optional[str] = None
    store_logo: Optional[str] = None
    store_id: Optional[str] = None


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
        from_attributes = True


# ─── CHAT SCHEMAS ─────────────────────────────────────────────────────────────

class ConversationInitiate(BaseModel):
    listing_id: str


class ConversationOut(BaseModel):
    id: str
    listing_id: str
    buyer_id: str
    seller_id: str
    status: str
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None
    buyer_unread: int = 0
    seller_unread: int = 0
    # Annotated server-side per requesting user
    unread_count: Optional[int] = 0
    my_role: Optional[str] = None       # "buyer" | "seller"
    listing: Optional[dict] = None      # joined listing snapshot
    other_participant_name: Optional[str] = None
    other_participant_image: Optional[str] = None
    other_participant_type: Optional[str] = None # "store" | "individual"
    store_name: Optional[str] = None     # Specific field for store name if applicable
    store_logo: Optional[str] = None     # Specific field for store logo if applicable
    sender_name: Optional[str] = None    # Alias for other_participant_name
    sender_logo: Optional[str] = None    # Alias for other_participant_image
    created_at: Optional[str] = None


class ConversationListResponse(BaseModel):
    conversations: List[ConversationOut]
    total: int
    page: int
    limit: int


class MessageCreate(BaseModel):
    content: Optional[str] = None
    message_type: str = "text"          # text | image | offer
    media_url: Optional[str] = None
    offer_amount: Optional[float] = None


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    sender_name: Optional[str] = None
    sender_image: Optional[str] = None
    sender_logo: Optional[str] = None    # Alias for sender_image
    store_name: Optional[str] = None
    store_logo: Optional[str] = None
    content: Optional[str] = None
    message_type: str
    media_url: Optional[str] = None
    offer_amount: Optional[float] = None
    offer_status: Optional[str] = None
    is_read: bool
    is_deleted: bool
    created_at: str

# ─── TRANSACTIONS ─────────────────────────────────────────────────────────────

class TransactionOut(BaseModel):
    id: str
    user_id: str
    amount: float
    currency: str
    status: str
    payment_method: Optional[str] = None
    paymob_transaction_id: Optional[str] = None
    metadata: Optional[dict] = None
    created_at: str

class TransactionListResponse(BaseModel):
    transactions: List[TransactionOut]
    total: int
    page: int
    limit: int
    pages: int

class AdminTransactionListItem(BaseModel):
    id: str
    paymob_transaction_id: Optional[str] = None
    created_at: str
    user_name: Optional[str] = None
    status: str
    amount: float
    currency: str

class AdminTransactionListResponse(BaseModel):
    transactions: List[AdminTransactionListItem]
    total: int
    page: int
    limit: int
    pages: int

class AdminTransactionDetail(TransactionOut):
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    user_phone: Optional[str] = None
