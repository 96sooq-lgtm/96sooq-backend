from fastapi import APIRouter, HTTPException, status, Query, Depends
from models import schemas
from db.supabase_client import db
from utils.auth import get_current_admin
from utils.helpers import get_viewable_image_url
from utils.logger import get_logger
from typing import Optional, List
import json

logger = get_logger(__name__)

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
def create_category(payload: schemas.CategoryCreate):
    """
    Create a category or subcategory.
    - For categories: name_en, name_ar, image_url (from /storage/upload)
    - For subcategories: name_en, name_ar, image_url, parent_id
      Subcategories automatically get default attributes_schema if not provided.
    """
    try:
        logger.info(f"Creating category: name_en='{payload.name_en}', parent_id={payload.parent_id}")

        # Check existence by English name
        existing = db.select("categories", filters={"name_en": payload.name_en})
        if existing:
            logger.warning(f"Category creation failed: name '{payload.name_en}' already exists (id={existing[0]['id']})")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category with name '{payload.name_en}' already exists"
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
                logger.warning(f"Category creation failed: parent_id '{payload.parent_id}' not found")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Parent category with id '{payload.parent_id}' not found"
                )
            data["parent_id"] = payload.parent_id
            logger.info(f"Creating subcategory under parent '{parent['name_en']}'")

            # Set default attributes_schema for subcategories if not provided
            if not payload.attributes_schema:
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
                        "name": "images",
                        "type": "multi_file",
                        "label_en": "Images",
                        "label_ar": "الصور",
                        "required": False,
                        "accept": "image/*",
                        "multiple": True
                    }
                ]
                data["attributes_schema"] = default_attributes
            else:
                data["attributes_schema"] = payload.attributes_schema
        elif payload.attributes_schema:
            data["attributes_schema"] = payload.attributes_schema

        category = db.insert("categories", data)

        if not category:
            logger.error(f"Category creation failed: db.insert returned None for '{payload.name_en}'")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create category. Database did not return a result."
            )

        # Ensure image URL is viewable
        if category.get("image_url"):
            category["image_url"] = get_viewable_image_url(category["image_url"])

        logger.info(f"Category created successfully: id={category['id']}, name='{category['name_en']}'")
        return category

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating category '{payload.name_en}': {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the category."
        )


@admin_router.get("/list", response_model=list[schemas.CategoryOut])
def list_root_categories(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    is_active: Optional[bool] = Query(None, description="Filter by active status. If omitted, returns all.")
):
    """
    Returns only ROOT categories (parent_id is null)
    """
    try:
        logger.info(f"Listing root categories: skip={skip}, limit={limit}, is_active={is_active}")

        def query_func(table):
            query = table.select("*").is_("parent_id", "null")
            query = query.eq("is_deleted", False)
            if is_active is not None:
                query = query.eq("is_active", is_active)
            return query.range(skip, skip + limit - 1).order("created_at")

        result = db.query("categories", query_func)
        categories = result.data if result.data else []

        for category in categories:
            if category.get("image_url"):
                category["image_url"] = get_viewable_image_url(category["image_url"])

        logger.info(f"Found {len(categories)} root categories")
        return categories

    except Exception as e:
        logger.error(f"Error listing root categories: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve root categories."
        )


@admin_router.get("/subcategories", response_model=list[schemas.CategoryOut])
def list_all_subcategories(
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
    try:
        logger.info(f"Listing subcategories: parent_id={parent_id}, skip={skip}, limit={limit}, is_active={is_active}")

        def query_func(table):
            query = table.select("*")
            query = query.not_.is_("parent_id", "null")
            query = query.eq("is_deleted", False)
            if parent_id:
                query = query.eq("parent_id", parent_id)
            if is_active is not None:
                query = query.eq("is_active", is_active)
            return query.range(skip, skip + limit - 1).order("created_at")

        result = db.query("categories", query_func)
        subcategories = result.data if result.data else []

        # Batch fetch parent categories — 1 query instead of N
        parent_ids = list({c["parent_id"] for c in subcategories if c.get("parent_id")})
        parents = db.select_in("categories", "id", parent_ids) if parent_ids else []
        parent_cache = {p["id"]: p for p in parents}

        for category in subcategories:
            if category.get("image_url"):
                category["image_url"] = get_viewable_image_url(category["image_url"])

            pid = category.get("parent_id")
            if pid:
                parent = parent_cache.get(pid, {})
                category["parent_name_en"] = parent.get("name_en")
                category["parent_name_ar"] = parent.get("name_ar")

        logger.info(f"Found {len(subcategories)} subcategories" + (f" for parent_id={parent_id}" if parent_id else ""))
        return subcategories

    except Exception as e:
        logger.error(f"Error listing subcategories: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve subcategories."
        )


@admin_router.get("/", response_model=list[schemas.CategoryOut])
def list_categories_admin(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500)
):
    """
    Admin: List ALL categories (including deleted and inactive) with pagination.
    """
    try:
        logger.info(f"Admin listing all categories: skip={skip}, limit={limit}")

        def query_func(table):
            return table.select("*").range(skip, skip + limit - 1).order("created_at")

        result = db.query("categories", query_func)
        categories = result.data if result.data else []

        for category in categories:
            if category.get("image_url"):
                category["image_url"] = get_viewable_image_url(category["image_url"])

        logger.info(f"Admin: returned {len(categories)} categories")
        return categories

    except Exception as e:
        logger.error(f"Error in admin category listing: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve categories."
        )


@admin_router.get("/{category_id}", response_model=schemas.CategoryOut)
def get_category(category_id: str):
    """Admin: Get a single category by ID."""
    try:
        logger.info(f"Fetching category: id={category_id}")

        category = db.select_one("categories", category_id)
        if not category:
            logger.warning(f"Category not found: id={category_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category with id '{category_id}' not found"
            )

        if category.get("image_url"):
            category["image_url"] = get_viewable_image_url(category["image_url"])

        return category

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching category {category_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve category."
        )


@admin_router.put("/{category_id}", response_model=schemas.CategoryOut)
def update_category(category_id: str, payload: schemas.CategoryUpdate):
    """
    Update a category or subcategory.
    Use image_url from /storage/upload endpoint.
    """
    try:
        logger.info(f"Updating category: id={category_id}, fields={payload.dict(exclude_unset=True)}")

        existing = db.select_one("categories", category_id)
        if not existing:
            logger.warning(f"Update failed: category '{category_id}' not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category with id '{category_id}' not found"
            )

        update_data = {}

        # Handle name update if provided
        if payload.name_en is not None or payload.name_ar is not None:
            new_en = payload.name_en if payload.name_en is not None else existing["name_en"]
            new_ar = payload.name_ar if payload.name_ar is not None else existing["name_ar"]

            if new_en != existing["name_en"]:
                duplicate = db.select("categories", filters={"name_en": new_en})
                if duplicate:
                    logger.warning(f"Update failed: name '{new_en}' already taken by category {duplicate[0]['id']}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Category with name '{new_en}' already exists"
                    )

            update_data["name_en"] = new_en
            update_data["name_ar"] = new_ar

        if payload.is_active is not None:
            update_data["is_active"] = payload.is_active

        if payload.image_url is not None:
            update_data["image_url"] = payload.image_url

        if payload.parent_id is not None:
            if payload.parent_id == category_id:
                logger.warning(f"Update failed: category '{category_id}' cannot be its own parent")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Category cannot be its own parent"
                )
            parent = db.select_one("categories", payload.parent_id)
            if not parent:
                logger.warning(f"Update failed: parent_id '{payload.parent_id}' not found")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Parent category with id '{payload.parent_id}' not found"
                )
            update_data["parent_id"] = payload.parent_id

        if payload.attributes_schema is not None:
            update_data["attributes_schema"] = payload.attributes_schema

        if not update_data:
            logger.info(f"No fields to update for category '{category_id}'")
            if existing.get("image_url"):
                existing["image_url"] = get_viewable_image_url(existing["image_url"])
            return existing

        updated = db.update("categories", category_id, update_data)
        if not updated:
            logger.error(f"db.update returned None for category '{category_id}'")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update category. Database did not return a result."
            )

        if updated.get("image_url"):
            updated["image_url"] = get_viewable_image_url(updated["image_url"])

        logger.info(f"Category updated successfully: id={category_id}, fields={list(update_data.keys())}")
        return updated

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error updating category {category_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the category."
        )


@admin_router.delete("/{category_id}")
def delete_category(category_id: str):
    """Admin: Soft-delete a category (sets is_deleted=True)."""
    try:
        logger.info(f"Deleting category: id={category_id}")

        existing = db.select_one("categories", category_id)
        if not existing:
            logger.warning(f"Delete failed: category '{category_id}' not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category with id '{category_id}' not found"
            )

        if existing.get("is_deleted"):
            logger.warning(f"Delete failed: category '{category_id}' is already deleted")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Category '{existing['name_en']}' is already deleted"
            )

        # Check if category has active subcategories
        children = db.select("categories", filters={"parent_id": category_id})
        active_children = [c for c in children if not c.get("is_deleted")]
        if active_children:
            logger.warning(f"Delete failed: category '{category_id}' has {len(active_children)} active subcategories")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete category '{existing['name_en']}' — it has {len(active_children)} active subcategories. Delete them first."
            )

        updated = db.update("categories", category_id, {"is_deleted": True})
        if not updated:
            logger.error(f"db.update returned None when deleting category '{category_id}'")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete category. Database did not return a result."
            )

        logger.info(f"Category soft-deleted: id={category_id}, name='{existing['name_en']}'")
        return {"message": f"Category '{existing['name_en']}' deleted successfully", "id": category_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting category {category_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the category."
        )


@admin_router.post("/{category_id}/attributes", response_model=schemas.CategoryOut, status_code=status.HTTP_201_CREATED)
def add_subcategory_attribute(
    category_id: str,
    attribute: schemas.AttributeDefinition
):
    """
    Admin: Add a single attribute to a subcategory's schema.
    Appends to the existing list — does NOT replace everything.
    """
    try:
        logger.info(f"Adding attribute '{attribute.name}' to category {category_id}")

        category = db.select_one("categories", category_id)
        if not category:
            logger.warning(f"Add attribute failed: category '{category_id}' not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category with id '{category_id}' not found"
            )

        if not category.get("parent_id"):
            logger.warning(f"Add attribute failed: '{category_id}' is a root category, not a subcategory")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot add attributes to root category '{category['name_en']}'. Attributes belong to subcategories."
            )

        current_schema = category.get("attributes_schema") or []

        if any(a.get("name") == attribute.name for a in current_schema):
            logger.warning(f"Add attribute failed: '{attribute.name}' already exists in category '{category_id}'")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Attribute '{attribute.name}' already exists in '{category['name_en']}'"
            )

        current_schema.append(attribute.model_dump())
        updated = db.update("categories", category_id, {"attributes_schema": current_schema})
        if not updated:
            logger.error(f"db.update returned None when adding attribute to '{category_id}'")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to add attribute. Database did not return a result."
            )

        logger.info(f"Attribute '{attribute.name}' added to category '{category['name_en']}' (total: {len(current_schema)})")
        logger.debug(f"Updated schema for {category_id}: {json.dumps(current_schema, ensure_ascii=False)}")
        return updated

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error adding attribute to {category_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while adding the attribute."
        )


@admin_router.patch("/{category_id}/attributes", response_model=schemas.CategoryOut)
def replace_subcategory_attributes(
    category_id: str,
    attributes: List[schemas.AttributeDefinition]
):
    """
    Admin: Replace the FULL attributes_schema of a subcategory.
    Use this to set all attributes at once.
    """
    try:
        logger.info(f"Replacing all attributes for category {category_id} ({len(attributes)} attributes)")

        category = db.select_one("categories", category_id)
        if not category:
            logger.warning(f"Replace attributes failed: category '{category_id}' not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category with id '{category_id}' not found"
            )

        if not category.get("parent_id"):
            logger.warning(f"Replace attributes failed: '{category_id}' is a root category")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot set attributes on root category '{category['name_en']}'. Attributes belong to subcategories."
            )

        # Check for duplicate attribute names in the new list
        names = [a.name for a in attributes]
        duplicates = [n for n in names if names.count(n) > 1]
        if duplicates:
            logger.warning(f"Replace attributes failed: duplicate names detected: {set(duplicates)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Duplicate attribute names found: {list(set(duplicates))}"
            )

        new_schema = [a.model_dump() for a in attributes]
        logger.info(f"Setting {len(new_schema)} attributes for category {category_id}")
        
        updated = db.update("categories", category_id, {"attributes_schema": new_schema})
        if not updated:
            logger.error(f"db.update returned None when replacing attributes for '{category_id}'")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update attributes. Database did not return a result."
            )

        logger.info(f"Attributes replaced for category '{category['name_en']}': {names}")
        logger.debug(f"New attributes_schema for {category_id}: {json.dumps(new_schema, ensure_ascii=False)}")
        return updated

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error replacing attributes for {category_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating attributes."
        )


@admin_router.delete("/{category_id}/attributes/{attribute_name}", response_model=schemas.CategoryOut)
def delete_subcategory_attribute(category_id: str, attribute_name: str):
    """
    Admin: Remove a single attribute by its name.
    Example: DELETE /api/admin/categories/{id}/attributes/fuel
    """
    try:
        logger.info(f"Deleting attribute '{attribute_name}' from category {category_id}")

        category = db.select_one("categories", category_id)
        if not category:
            logger.warning(f"Delete attribute failed: category '{category_id}' not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category with id '{category_id}' not found"
            )

        current_schema = category.get("attributes_schema") or []
        new_schema = [attr for attr in current_schema if attr.get("name") != attribute_name]

        if len(new_schema) == len(current_schema):
            logger.warning(f"Delete attribute failed: '{attribute_name}' not found in category '{category_id}'")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Attribute '{attribute_name}' not found in category '{category['name_en']}'"
            )

        updated = db.update("categories", category_id, {"attributes_schema": new_schema})
        if not updated:
            logger.error(f"db.update returned None when deleting attribute from '{category_id}'")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete attribute. Database did not return a result."
            )

        logger.info(f"Attribute '{attribute_name}' deleted from category '{category['name_en']}' (remaining: {len(new_schema)})")
        return updated

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting attribute '{attribute_name}' from {category_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the attribute."
        )


# -------------------------------------------------
# USER/PUBLIC ENDPOINTS
# -------------------------------------------------

@user_router.get("/", response_model=list[schemas.CategoryOut])
def list_active_categories(
    parent_id: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500)
):
    """Public: List active, non-deleted categories."""
    try:
        logger.info(f"Public category listing: parent_id={parent_id}, skip={skip}, limit={limit}")

        def query_func(table):
            query = table.select("*").eq("is_active", True).eq("is_deleted", False)
            if parent_id:
                query = query.eq("parent_id", parent_id)
            else:
                query = query.is_("parent_id", "null")
            return query.range(skip, skip + limit - 1).order("created_at")

        result = db.query("categories", query_func)
        categories = result.data if result.data else []

        for category in categories:
            if category.get("image_url"):
                category["image_url"] = get_viewable_image_url(category["image_url"])

        logger.info(f"Public: returned {len(categories)} categories" + (f" for parent_id={parent_id}" if parent_id else " (root)"))
        return categories

    except Exception as e:
        logger.error(f"Error in public category listing: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve categories."
        )


@user_router.get("/{category_id}/is-leaf")
def check_category_is_leaf(category_id: str):
    """Public: Check if a category is a leaf node (has no children)."""
    try:
        children = db.select("categories", filters={"parent_id": category_id})
        is_leaf = not bool(children)
        logger.info(f"Leaf check: category_id={category_id}, is_leaf={is_leaf}")
        return {"is_leaf": is_leaf, "id": category_id}
    except Exception as e:
        logger.error(f"Error checking leaf status for {category_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check category status."
        )
