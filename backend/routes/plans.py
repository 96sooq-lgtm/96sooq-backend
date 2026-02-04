from fastapi import APIRouter, HTTPException, status, Depends
from models import schemas
from db.supabase_client import db
from utils.auth import get_current_admin
from typing import List

router = APIRouter(
    prefix="/api/plans",
    tags=["plans"]
)

@router.post("/", response_model=schemas.PlanOut)
async def create_plan(
    payload: schemas.PlanCreate,
    current_admin: dict = Depends(get_current_admin)
):
    plan = db.insert("pricing_plans", payload.dict())
    if not plan:
        raise HTTPException(status_code=500, detail="Failed to create plan")
    return plan

@router.get("/", response_model=List[schemas.PlanOut])
async def list_plans(type: str = None):
    filters = {}
    if type:
        filters["type"] = type
    return db.select("pricing_plans", filters=filters)
