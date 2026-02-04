from fastapi import APIRouter, HTTPException, status, Depends
from models import schemas
from db.supabase_client import db
from utils.auth import get_current_customer
from typing import List

router = APIRouter(
    prefix="/api/ads",
    tags=["ads"]
)

@router.post("/", response_model=schemas.AdBannerOut)
async def create_ad(
    payload: schemas.AdBannerCreate,
    current_user: dict = Depends(get_current_customer)
):
    data = payload.dict()
    data["user_id"] = current_user["id"]
    data["status"] = "pending_payment"
    
    ad = db.insert("ad_banners", data)
    if not ad:
        raise HTTPException(status_code=500, detail="Failed to create ad")
        
    return ad

@router.get("/", response_model=List[schemas.AdBannerOut])
async def list_ads():
    # Only active ads
    return db.select("ad_banners", filters={"status": "active"})
