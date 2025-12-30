from fastapi import APIRouter, HTTPException, status, Query
from models import schemas
from db.supabase_client import db
from typing import Optional

# Admin routes (full CRUD)
admin_router = APIRouter(
    prefix="/api/admin/listings",
    tags=["admin-listings"]
)

# Public routes
public_router = APIRouter(
    prefix="/api/listings",
    tags=["listings"]
)

# User routes
user_router = APIRouter(
    prefix="/api/user/listings",
    tags=["user-listings"]
)


# ============ ADMIN ROUTES (FULL CRUD) ============

@admin_router.post("", response_model=schemas.ListingOut)
async def create_listing_admin(payload: schemas.ListingCreate):
    """Create a new listing (admin only)"""
    # Verify category exists
    category = db.select_one("categories", payload.category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    # Verify user exists
    user = db.select_one("users", payload.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Create listing
    created = db.insert("listings", {
        "title": payload.title,
        "description": payload.description,
        "category_id": payload.category_id,
        "user_id": payload.user_id,
        "price": payload.price,
        "location": payload.location,
        "phone_number": payload.phone_number,
        "image_url": payload.image_url,
        "is_active": payload.is_active
    })
    
    if not created:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create listing"
        )
    
    return {
        "id": created.get("id"),
        "title": created.get("title"),
        "description": created.get("description"),
        "category_id": created.get("category_id"),
        "user_id": created.get("user_id"),
        "price": created.get("price"),
        "location": created.get("location"),
        "phone_number": created.get("phone_number"),
        "image_url": created.get("image_url"),
        "is_active": created.get("is_active"),
        "created_at": created.get("created_at"),
        "updated_at": created.get("updated_at")
    }


@admin_router.get("", response_model=list[schemas.ListingOut])
async def list_all_listings_admin(skip: int = 0, limit: int = 100):
    """List all listings (admin only) - with pagination"""
    def query_func(table):
        return table.select("*").range(skip, skip + limit - 1)
    
    result = db.query("listings", query_func)
    
    if not result:
        return []
    
    return [
        {
            "id": listing.get("id"),
            "title": listing.get("title"),
            "description": listing.get("description"),
            "category_id": listing.get("category_id"),
            "user_id": listing.get("user_id"),
            "price": listing.get("price"),
            "location": listing.get("location"),
            "phone_number": listing.get("phone_number"),
            "image_url": listing.get("image_url"),
            "is_active": listing.get("is_active"),
            "created_at": listing.get("created_at"),
            "updated_at": listing.get("updated_at")
        }
        for listing in result
    ]


@admin_router.get("/{listing_id}", response_model=schemas.ListingOut)
async def get_listing_admin(listing_id: str):
    """Get a specific listing by ID (admin only)"""
    listing = db.select_one("listings", listing_id)
    
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found"
        )
    
    return {
        "id": listing.get("id"),
        "title": listing.get("title"),
        "description": listing.get("description"),
        "category_id": listing.get("category_id"),
        "user_id": listing.get("user_id"),
        "price": listing.get("price"),
        "location": listing.get("location"),
        "phone_number": listing.get("phone_number"),
        "image_url": listing.get("image_url"),
        "is_active": listing.get("is_active"),
        "created_at": listing.get("created_at"),
        "updated_at": listing.get("updated_at")
    }


@admin_router.put("/{listing_id}", response_model=schemas.ListingOut)
async def update_listing_admin(listing_id: str, payload: schemas.ListingUpdate):
    """Update a listing (admin only)"""
    # Check if listing exists
    listing = db.select_one("listings", listing_id)
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found"
        )
    
    # Prepare update data
    update_data = {}
    
    if payload.title is not None:
        update_data["title"] = payload.title
    
    if payload.description is not None:
        update_data["description"] = payload.description
    
    if payload.category_id is not None:
        # Verify new category exists
        category = db.select_one("categories", payload.category_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )
        update_data["category_id"] = payload.category_id
    
    if payload.price is not None:
        update_data["price"] = payload.price
    
    if payload.location is not None:
        update_data["location"] = payload.location
    
    if payload.phone_number is not None:
        update_data["phone_number"] = payload.phone_number
    
    if payload.image_url is not None:
        update_data["image_url"] = payload.image_url
    
    if payload.is_active is not None:
        update_data["is_active"] = payload.is_active
    
    if not update_data:
        # Return unchanged listing if no fields provided
        return {
            "id": listing.get("id"),
            "title": listing.get("title"),
            "description": listing.get("description"),
            "category_id": listing.get("category_id"),
            "user_id": listing.get("user_id"),
            "price": listing.get("price"),
            "location": listing.get("location"),
            "phone_number": listing.get("phone_number"),
            "image_url": listing.get("image_url"),
            "is_active": listing.get("is_active"),
            "created_at": listing.get("created_at"),
            "updated_at": listing.get("updated_at")
        }
    
    # Update listing
    updated = db.update("listings", listing_id, update_data)
    
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update listing"
        )
    
    return {
        "id": updated.get("id"),
        "title": updated.get("title"),
        "description": updated.get("description"),
        "category_id": updated.get("category_id"),
        "user_id": updated.get("user_id"),
        "price": updated.get("price"),
        "location": updated.get("location"),
        "phone_number": updated.get("phone_number"),
        "image_url": updated.get("image_url"),
        "is_active": updated.get("is_active"),
        "created_at": updated.get("created_at"),
        "updated_at": updated.get("updated_at")
    }


@admin_router.delete("/{listing_id}")
async def delete_listing_admin(listing_id: str):
    """Delete a listing (admin only)"""
    # Check if listing exists
    listing = db.select_one("listings", listing_id)
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found"
        )
    
    # Delete listing
    deleted = db.delete("listings", listing_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete listing"
        )
    
    return {"message": "Listing deleted successfully", "id": listing_id}


# ============ PUBLIC ROUTES ============

@public_router.get("", response_model=list[schemas.ListingOut])
async def list_active_listings(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    category_id: Optional[str] = None,
    location: Optional[str] = None
):
    """
    List all active listings (public endpoint)
    Optional filters: category_id, location
    """
    def query_func(table):
        query = table.select("*").eq("is_active", True)
        
        if category_id:
            query = query.eq("category_id", category_id)
        
        if location:
            query = query.eq("location", location)
        
        return query.range(skip, skip + limit - 1)
    
    result = db.query("listings", query_func)
    
    if not result:
        return []
    
    return [
        {
            "id": listing.get("id"),
            "title": listing.get("title"),
            "description": listing.get("description"),
            "category_id": listing.get("category_id"),
            "user_id": listing.get("user_id"),
            "price": listing.get("price"),
            "location": listing.get("location"),
            "phone_number": listing.get("phone_number"),
            "image_url": listing.get("image_url"),
            "is_active": listing.get("is_active"),
            "created_at": listing.get("created_at"),
            "updated_at": listing.get("updated_at")
        }
        for listing in result
    ]


@public_router.get("/{listing_id}", response_model=schemas.ListingOut)
async def get_listing_public(listing_id: str):
    """Get a specific active listing by ID (public)"""
    listing = db.select_one("listings", listing_id)
    
    if not listing or not listing.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found"
        )
    
    return {
        "id": listing.get("id"),
        "title": listing.get("title"),
        "description": listing.get("description"),
        "category_id": listing.get("category_id"),
        "user_id": listing.get("user_id"),
        "price": listing.get("price"),
        "location": listing.get("location"),
        "phone_number": listing.get("phone_number"),
        "image_url": listing.get("image_url"),
        "is_active": listing.get("is_active"),
        "created_at": listing.get("created_at"),
        "updated_at": listing.get("updated_at")
    }


# ============ USER ROUTES ============

@user_router.post("", response_model=schemas.ListingOut)
async def create_user_listing(payload: schemas.ListingCreate):
    """Create a new listing for authenticated user"""
    # Verify category exists
    category = db.select_one("categories", payload.category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    # Verify user exists
    user = db.select_one("users", payload.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Create listing
    created = db.insert("listings", {
        "title": payload.title,
        "description": payload.description,
        "category_id": payload.category_id,
        "user_id": payload.user_id,
        "price": payload.price,
        "location": payload.location,
        "phone_number": payload.phone_number,
        "image_url": payload.image_url,
        "is_active": payload.is_active
    })
    
    if not created:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create listing"
        )
    
    return {
        "id": created.get("id"),
        "title": created.get("title"),
        "description": created.get("description"),
        "category_id": created.get("category_id"),
        "user_id": created.get("user_id"),
        "price": created.get("price"),
        "location": created.get("location"),
        "phone_number": created.get("phone_number"),
        "image_url": created.get("image_url"),
        "is_active": created.get("is_active"),
        "created_at": created.get("created_at"),
        "updated_at": created.get("updated_at")
    }


@user_router.get("/user/{user_id}", response_model=list[schemas.ListingOut])
async def get_user_listings(user_id: str, skip: int = 0, limit: int = 100):
    """Get all listings for a specific user"""
    # Verify user exists
    user = db.select_one("users", user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    def query_func(table):
        return table.select("*").eq("user_id", user_id).range(skip, skip + limit - 1)
    
    result = db.query("listings", query_func)
    
    if not result:
        return []
    
    return [
        {
            "id": listing.get("id"),
            "title": listing.get("title"),
            "description": listing.get("description"),
            "category_id": listing.get("category_id"),
            "user_id": listing.get("user_id"),
            "price": listing.get("price"),
            "location": listing.get("location"),
            "phone_number": listing.get("phone_number"),
            "image_url": listing.get("image_url"),
            "is_active": listing.get("is_active"),
            "created_at": listing.get("created_at"),
            "updated_at": listing.get("updated_at")
        }
        for listing in result
    ]


@user_router.put("/{listing_id}", response_model=schemas.ListingOut)
async def update_user_listing(listing_id: str, payload: schemas.ListingUpdate):
    """Update user's own listing"""
    # Check if listing exists
    listing = db.select_one("listings", listing_id)
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found"
        )
    
    # Prepare update data
    update_data = {}
    
    if payload.title is not None:
        update_data["title"] = payload.title
    
    if payload.description is not None:
        update_data["description"] = payload.description
    
    if payload.category_id is not None:
        # Verify new category exists
        category = db.select_one("categories", payload.category_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )
        update_data["category_id"] = payload.category_id
    
    if payload.price is not None:
        update_data["price"] = payload.price
    
    if payload.location is not None:
        update_data["location"] = payload.location
    
    if payload.phone_number is not None:
        update_data["phone_number"] = payload.phone_number
    
    if payload.image_url is not None:
        update_data["image_url"] = payload.image_url
    
    if payload.is_active is not None:
        update_data["is_active"] = payload.is_active
    
    if not update_data:
        # Return unchanged listing if no fields provided
        return {
            "id": listing.get("id"),
            "title": listing.get("title"),
            "description": listing.get("description"),
            "category_id": listing.get("category_id"),
            "user_id": listing.get("user_id"),
            "price": listing.get("price"),
            "location": listing.get("location"),
            "phone_number": listing.get("phone_number"),
            "image_url": listing.get("image_url"),
            "is_active": listing.get("is_active"),
            "created_at": listing.get("created_at"),
            "updated_at": listing.get("updated_at")
        }
    
    # Update listing
    updated = db.update("listings", listing_id, update_data)
    
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update listing"
        )
    
    return {
        "id": updated.get("id"),
        "title": updated.get("title"),
        "description": updated.get("description"),
        "category_id": updated.get("category_id"),
        "user_id": updated.get("user_id"),
        "price": updated.get("price"),
        "location": updated.get("location"),
        "phone_number": updated.get("phone_number"),
        "image_url": updated.get("image_url"),
        "is_active": updated.get("is_active"),
        "created_at": updated.get("created_at"),
        "updated_at": updated.get("updated_at")
    }


@user_router.delete("/{listing_id}")
async def delete_user_listing(listing_id: str):
    """Delete user's own listing"""
    # Check if listing exists
    listing = db.select_one("listings", listing_id)
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found"
        )
    
    # Delete listing
    deleted = db.delete("listings", listing_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete listing"
        )
    
    return {"message": "Listing deleted successfully", "id": listing_id}
