from fastapi import APIRouter, HTTPException, status, Depends, Query
from models import schemas
from db.supabase_client import db
from utils.auth import get_current_customer
from typing import List

router = APIRouter(
    prefix="/api/reviews",
    tags=["reviews"]
)

@router.post("/", response_model=schemas.StoreReviewOut, status_code=status.HTTP_201_CREATED)
async def create_review(
    payload: schemas.StoreReviewCreate,
    current_user: dict = Depends(get_current_customer)
):
    # Verify store exists
    store = db.select_one("stores", payload.store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
        
    # Prevent self-review?
    if store["user_id"] == current_user["id"]:
        raise HTTPException(status_code=400, detail="Cannot review your own store")
        
    data = payload.dict()
    data["reviewer_id"] = current_user["id"]
    
    review = db.insert("store_reviews", data)
    if not review:
        raise HTTPException(status_code=500, detail="Failed to create review")
        
    return review

@router.get("/store/{store_id}", response_model=List[schemas.StoreReviewOut])
async def list_store_reviews(store_id: str):
    return db.select("store_reviews", filters={"store_id": store_id})
