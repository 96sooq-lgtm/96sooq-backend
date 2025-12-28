from fastapi import APIRouter, HTTPException, status
from models import schemas
from db.supabase_client import db

# Admin routes (CRUD)
admin_router = APIRouter(
    prefix="/api/admin/categories",
    tags=["admin-categories"]
)

# Public routes
public_router = APIRouter(
    prefix="/api/categories",
    tags=["categories"]
)


# ============ ADMIN ROUTES ============

@admin_router.post("", response_model=schemas.CategoryOut)
async def create_category(payload: schemas.CategoryCreate):
    """Create a new category (admin only)"""
    # Check if category already exists
    existing = db.select("categories", filters={"name": payload.name})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category with this name already exists"
        )
    
    # Create category
    created = db.insert("categories", {
        "name": payload.name,
        "is_active": payload.is_active
    })
    
    if not created:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create category"
        )
    
    return {
        "id": created.get("id"),
        "name": created.get("name"),
        "is_active": created.get("is_active"),
        "created_at": created.get("created_at"),
        "updated_at": created.get("updated_at")
    }


@admin_router.get("", response_model=list[schemas.CategoryOut])
async def list_all_categories(skip: int = 0, limit: int = 100):
    """List all categories (admin only) - with pagination"""
    # Using custom query for pagination
    def query_func(table):
        return table.select("*").range(skip, skip + limit - 1)
    
    result = db.query("categories", query_func)
    
    if not result:
        return []
    
    return [
        {
            "id": cat.get("id"),
            "name": cat.get("name"),
            "is_active": cat.get("is_active"),
            "created_at": cat.get("created_at"),
            "updated_at": cat.get("updated_at")
        }
        for cat in result
    ]


@admin_router.get("/{category_id}", response_model=schemas.CategoryOut)
async def get_category(category_id: str):
    """Get a specific category by ID (admin only)"""
    category = db.select_one("categories", category_id)
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    return {
        "id": category.get("id"),
        "name": category.get("name"),
        "is_active": category.get("is_active"),
        "created_at": category.get("created_at"),
        "updated_at": category.get("updated_at")
    }


@admin_router.put("/{category_id}", response_model=schemas.CategoryOut)
async def update_category(category_id: str, payload: schemas.CategoryUpdate):
    """Update a category (admin only)"""
    # Check if category exists
    category = db.select_one("categories", category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    # Prepare update data (only include provided fields)
    update_data = {}
    if payload.name is not None:
        # Check if new name already exists (and is not the current category)
        existing = db.select("categories", filters={"name": payload.name})
        if existing and existing[0].get("id") != category_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category name already exists"
            )
        update_data["name"] = payload.name
    
    if payload.is_active is not None:
        update_data["is_active"] = payload.is_active
    
    if not update_data:
        # Return unchanged category if no fields provided
        return {
            "id": category.get("id"),
            "name": category.get("name"),
            "is_active": category.get("is_active"),
            "created_at": category.get("created_at"),
            "updated_at": category.get("updated_at")
        }
    
    # Update category
    updated = db.update("categories", category_id, update_data)
    
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update category"
        )
    
    return {
        "id": updated.get("id"),
        "name": updated.get("name"),
        "is_active": updated.get("is_active"),
        "created_at": updated.get("created_at"),
        "updated_at": updated.get("updated_at")
    }


@admin_router.delete("/{category_id}")
async def delete_category(category_id: str):
    """Delete a category (admin only)"""
    # Check if category exists
    category = db.select_one("categories", category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    # Delete category
    deleted = db.delete("categories", category_id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete category"
        )
    
    return {"message": "Category deleted successfully", "id": category_id}


# ============ PUBLIC ROUTES ============

@public_router.get("/active", response_model=list[schemas.CategoryOut])
async def list_active_categories(skip: int = 0, limit: int = 100):
    """List all active categories (public endpoint for frontend)"""
    # Fetch active categories with pagination
    def query_func(table):
        return table.select("*").eq("is_active", True).range(skip, skip + limit - 1)
    
    result = db.query("categories", query_func)
    
    if not result:
        return []
    
    return [
        {
            "id": cat.get("id"),
            "name": cat.get("name"),
            "is_active": cat.get("is_active"),
            "created_at": cat.get("created_at"),
            "updated_at": cat.get("updated_at")
        }
        for cat in result
    ]
