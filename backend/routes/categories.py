from fastapi import APIRouter, HTTPException, status, Query, Depends
from models import schemas
from db.supabase_client import db
from utils.auth import get_current_admin
from utils.translation import translate_text

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
# ADMIN ENDPOINTS
# -------------------------------------------------

@admin_router.post("/", response_model=schemas.CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(payload: schemas.CategoryCreate):
    # Auto-translate
    translations = translate_text(payload.name)
    name_en = translations["name_en"]
    name_ar = translations["name_ar"]

    # Check existence by English name
    existing = db.select("categories", filters={"name_en": name_en})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category with this name already exists"
        )

    # Prepare data for insertion
    data = payload.dict(exclude={"name"})
    data["name_en"] = name_en
    data["name_ar"] = name_ar

    category = db.insert("categories", data)
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create category"
        )
    
    return category


@admin_router.get("/", response_model=list[schemas.CategoryOut])
async def list_categories_admin(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500)
):
    def query_func(table):
        # Sort by English name for consistency, or created_at
        return table.select("*").range(skip, skip + limit - 1).order("created_at", desc=True)

    result = db.query("categories", query_func)
    return result.data if result.data else []


@admin_router.get("/{category_id}", response_model=schemas.CategoryOut)
async def get_category(category_id: str):
    category = db.select_one("categories", category_id)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    return category


@admin_router.put("/{category_id}", response_model=schemas.CategoryOut)
async def update_category(category_id: str, payload: schemas.CategoryUpdate):
    # Check if category exists
    existing = db.select_one("categories", category_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    update_data = {}
    
    # Handle name update if provided
    if payload.name:
        translations = translate_text(payload.name)
        new_en = translations["name_en"]
        new_ar = translations["name_ar"]
        
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

    if not update_data:
        return existing

    updated = db.update("categories", category_id, update_data)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update category"
        )
        
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

    success = db.delete("categories", category_id)
    if not success:
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
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500)
):
    def query_func(table):
        # Filter for active categories only
        return table.select("*").eq("is_active", True).range(skip, skip + limit - 1).order("name_en")

    result = db.query("categories", query_func)
    return result.data if result.data else []
