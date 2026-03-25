from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from app.schemas.routing import DepartmentSchema, OfficerSchema
from app.services import routing_service

router = APIRouter(tags=["routing"])

@router.get("/departments", response_model=List[DepartmentSchema])
async def get_departments():
    """
    Get all active departments.
    """
    return await routing_service.get_departments()

@router.get("/officers", response_model=List[OfficerSchema])
async def get_officers(
    ministry: Optional[str] = Query(None, description="Filter by ministry name"),
    department: Optional[str] = Query(None, description="Filter by department name"),
    city: Optional[str] = Query(None, description="Filter by city")
):
    """
    Get officers, optionally filtered by ministry, department and city.
    """
    return await routing_service.get_officers(ministry, department, city)
