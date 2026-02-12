from fastapi import APIRouter, Query, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel
from db.supabase_client import db

router = APIRouter(
    prefix="/api/locations",
    tags=["locations"]
)

class LocationOut(BaseModel):
    id: str
    name_en: str
    name_ar: str
    type: str # state, district, city
    parent_id: Optional[str] = None
    is_active: bool

@router.get("/", response_model=List[LocationOut])
async def list_locations(
    type: Optional[str] = Query(None, description="Filter by type: state, district, city"),
    parent_id: Optional[str] = Query(None, description="Filter by parent location ID"),
    is_active: bool = Query(True, description="Filter active locations")
):
    """
    List locations based on filters.
    - To get all States: `?type=state`
    - To get Districts in a State: `?type=district&parent_id={state_id}`
    - To get Cities in a District: `?type=city&parent_id={district_id}`
    """
    def query_func(table):
        query = table.select("*")
        
        if is_active:
             query = query.eq("is_active", True)
             
        if type:
            query = query.eq("type", type)
            
        if parent_id:
            query = query.eq("parent_id", parent_id)
            
        return query.order("name_en")

    result = db.query("locations", query_func)
    return result.data if result.data else []

@router.get("/{location_id}", response_model=LocationOut)
async def get_location(location_id: str):
    location = db.select_one("locations", location_id)
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    return location
