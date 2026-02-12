from fastapi import APIRouter, HTTPException, status, Query, Depends
from models import schemas
from db.supabase_client import db
from utils.auth import get_current_admin
from utils.storage import s3_client
from typing import Optional
import json

# Admin Router
admin_router = APIRouter(
    prefix="/api/admin/categories",
    tags=["admin-categories"],
    dependencies=[Depends(get_current_admin)]
)

# Public/User Router
user_router = APIRouter(
    prefix="/api/categories",
    tags=["categories"]
)

# -------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------

def get_viewable_image_url(image_url_or_path: Optional[str]) -> Optional[str]:
    """
    Convert image URL or file path to a viewable URL.
    - If it's already a full URL (http/https), return as-is
    - If it's a file_path (starts with folder name), generate presigned URL
    """
    if not image_url_or_path:
        return None
    
    # If it's already a full URL, return as-is
    if image_url_or_path.startswith(('http://', 'https://')):
        return image_url_or_path
    
    # If it's a file_path, generate presigned URL for viewing
    if s3_client:
        presigned_url = s3_client.generate_presigned_url(image_url_or_path, expiration=3600)
        return presigned_url if presigned_url else image_url_or_path
    
    return image_url_or_path


# -------------------------------------------------
# ADMIN ENDPOINTS
# -------------------------------------------------

@admin_router.post("/", response_model=schemas.CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(payload: schemas.CategoryCreate):
    """
    Create a category or subcategory.
    - For categories: name_en, name_ar, image_url (from /storage/upload)
    - For subcategories: name_en, name_ar, image_url, parent_id
      Subcategories automatically get default attributes_schema if not provided.
    """
    # Check existence by English name
    existing = db.select("categories", filters={"name_en": payload.name_en})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category with this name already exists"
        )

    # Prepare data for insertion
    data = {
        "name_en": payload.name_en,
        "name_ar": payload.name_ar,
        "is_active": payload.is_active
    }
    
    if payload.image_url:
        data["image_url"] = payload.image_url
        
    if payload.parent_id:
        # Verify parent exists
        parent = db.select_one("categories", payload.parent_id)
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent category not found"
            )
        data["parent_id"] = payload.parent_id
        
        # Set default attributes_schema for subcategories if not provided
        if not payload.attributes_schema:
            # Default attributes for subcategories: name, price, description, image/video
            default_attributes = [
                {
                    "name": "name",
                    "type": "text",
                    "label_en": "Name",
                    "label_ar": "الاسم",
                    "required": True
                },
                {
                    "name": "price",
                    "type": "number",
                    "label_en": "Price",
                    "label_ar": "السعر",
                    "required": True
                },
                {
                    "name": "description",
                    "type": "textarea",
                    "label_en": "Description",
                    "label_ar": "الوصف",
                    "required": False
                },
                {
                    "name": "image",
                    "type": "file",
                    "label_en": "Image",
                    "label_ar": "صورة",
                    "required": False,
                    "accept": "image/*"
                },
                {
                    "name": "video",
                    "type": "file",
                    "label_en": "Video",
                    "label_ar": "فيديو",
                    "required": False,
                    "accept": "video/*"
                }
            ]
            data["attributes_schema"] = default_attributes
        else:
            data["attributes_schema"] = payload.attributes_schema
    elif payload.attributes_schema:
        data["attributes_schema"] = payload.attributes_schema

    category = db.insert("categories", data)
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create category"
        )
    
    # Ensure image URL is viewable
    if category.get("image_url"):
        category["image_url"] = get_viewable_image_url(category["image_url"])
    
    return category

@admin_router.get("/list", response_model=list[schemas.CategoryOut])
async def list_root_categories(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    is_active: Optional[bool] = Query(None, description="Filter by active status. If omitted, returns all.")
):
    """
    Returns only ROOT categories (parent_id is null)
    """
    def query_func(table):
        query = table.select("*").is_("parent_id", "null")
        
        # Filter out deleted categories
        query = query.eq("is_deleted", False)
        
        if is_active is not None:
            query = query.eq("is_active", is_active)
            
        return query.range(skip, skip + limit - 1).order("name_en")

    result = db.query("categories", query_func)
    categories = result.data if result.data else []

    for category in categories:
        if category.get("image_url"):
            category["image_url"] = get_viewable_image_url(category["image_url"])

    return categories

@admin_router.get("/subcategories", response_model=list[schemas.CategoryOut])
async def list_all_subcategories(
    parent_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    is_active: Optional[bool] = Query(None, description="Filter by active status. If omitted, returns all.")
):
    """
    Returns only subcategories
    - If parent_id is given → returns subcategories of that parent
    - If not → returns ALL subcategories
    """
    def query_func(table):
        query = table.select("*")

        # Only records where parent_id is NOT null
        query = query.not_.is_("parent_id", "null")
        
        # Filter out deleted categories
        query = query.eq("is_deleted", False)

        if parent_id:
            query = query.eq("parent_id", parent_id)
            
        if is_active is not None:
            query = query.eq("is_active", is_active)

        return query.range(skip, skip + limit - 1).order("name_en")

    result = db.query("categories", query_func)
    subcategories = result.data if result.data else []

    for category in subcategories:
        if category.get("image_url"):
            category["image_url"] = get_viewable_image_url(category["image_url"])

    return subcategories


@admin_router.get("/", response_model=list[schemas.CategoryOut])
async def list_categories_admin(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500)
):
    def query_func(table):
        # Sort by English name for consistency, or created_at
        return table.select("*").range(skip, skip + limit - 1).order("created_at", desc=True)

    result = db.query("categories", query_func)
    categories = result.data if result.data else []
    
    # Ensure all image URLs are viewable
    for category in categories:
        if category.get("image_url"):
            category["image_url"] = get_viewable_image_url(category["image_url"])
    
    return categories


@admin_router.get("/{category_id}", response_model=schemas.CategoryOut)
async def get_category(category_id: str):
    category = db.select_one("categories", category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    # Ensure image URL is viewable
    if category.get("image_url"):
        category["image_url"] = get_viewable_image_url(category["image_url"])
    
    return category


@admin_router.put("/{category_id}", response_model=schemas.CategoryOut)
async def update_category(category_id: str, payload: schemas.CategoryUpdate):
    """
    Update a category or subcategory.
    Use image_url from /storage/upload endpoint.
    """
    # Check if category exists
    existing = db.select_one("categories", category_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    update_data = {}
    
    # Handle name update if provided
    if payload.name_en is not None or payload.name_ar is not None:
        new_en = payload.name_en if payload.name_en is not None else existing["name_en"]
        new_ar = payload.name_ar if payload.name_ar is not None else existing["name_ar"]
        
        # Check uniqueness if name changed
        if new_en != existing["name_en"]:
            duplicate = db.select("categories", filters={"name_en": new_en})
            if duplicate:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Category with this name already exists"
                )
        
        update_data["name_en"] = new_en
        update_data["name_ar"] = new_ar
    
    if payload.is_active is not None:
        update_data["is_active"] = payload.is_active

    if payload.image_url is not None:
        update_data["image_url"] = payload.image_url
        
    if payload.parent_id is not None:
        # Prevent self-parenting
        if payload.parent_id == category_id:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category cannot be its own parent"
            )
        # Verify parent exists
        parent = db.select_one("categories", payload.parent_id)
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent category not found"
            )
        update_data["parent_id"] = payload.parent_id

    if payload.attributes_schema is not None:
        update_data["attributes_schema"] = payload.attributes_schema

    if not update_data:
        # Ensure image URL is viewable even if no updates
        if existing.get("image_url"):
            existing["image_url"] = get_viewable_image_url(existing["image_url"])
        return existing

    updated = db.update("categories", category_id, update_data)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update category"
        )
    
    # Ensure image URL is viewable
    if updated.get("image_url"):
        updated["image_url"] = get_viewable_image_url(updated["image_url"])
        
    return updated


@admin_router.delete("/{category_id}")
async def delete_category(category_id: str):
    # Check if category exists
    existing = db.select_one("categories", category_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )

    # Soft delete: Update is_deleted = True
    updated = db.update("categories", category_id, {"is_deleted": True})
    if not updated:
        # If update returns None, it might mean the ID doesn't exist (though we checked) or DB error
        # Re-check existence to be sure
        check = db.select_one("categories", category_id)
        if not check:
             raise HTTPException(status_code=404, detail="Category not found")
             
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete category"
        )
        
    return {"message": "Category deleted successfully", "id": category_id}


# -------------------------------------------------
# USER/PUBLIC ENDPOINTS
# -------------------------------------------------

@user_router.get("/", response_model=list[schemas.CategoryOut])
async def list_active_categories(
    parent_id: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500)
):
    def query_func(table):
        # Filter for active categories only and not deleted
        query = table.select("*").eq("is_active", True).eq("is_deleted", False)
        
        if parent_id:
            query = query.eq("parent_id", parent_id)
        else:
            # If no parent_id, fetch root categories (parent_id is null)
            query = query.is_("parent_id", "null")
            
        return query.range(skip, skip + limit - 1).order("name_en")

    result = db.query("categories", query_func)
    categories = result.data if result.data else []
    
    # Ensure all image URLs are viewable for e-commerce display
    for category in categories:
        if category.get("image_url"):
            category["image_url"] = get_viewable_image_url(category["image_url"])
    
    return categories


@user_router.get("/{category_id}/is-leaf")
async def check_category_is_leaf(category_id: str):
    # A category is a leaf if it has no children
    children = db.select("categories", filters={"parent_id": category_id})
    return {"is_leaf": not bool(children), "id": category_id}



