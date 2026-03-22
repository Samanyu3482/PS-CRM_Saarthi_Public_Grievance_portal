from fastapi import APIRouter, Depends
from app.schemas.user import UserInDB, RoleEnum
from app.api.deps import RoleChecker
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/heatmap")
async def heatmap(current_user: UserInDB = Depends(RoleChecker([RoleEnum.mp_mla, RoleEnum.ministry]))):
    return await analytics_service.get_heatmap()

@router.get("/trends")
async def trends(current_user: UserInDB = Depends(RoleChecker([RoleEnum.mp_mla, RoleEnum.ministry]))):
    return await analytics_service.get_trends()

@router.get("/departments")
async def departments_analytics(current_user: UserInDB = Depends(RoleChecker([RoleEnum.ministry]))):
    return await analytics_service.get_departments_analytics()

@router.get("/crisis")
async def crisis(current_user: UserInDB = Depends(RoleChecker([RoleEnum.ministry]))):
    return await analytics_service.get_crisis_alerts()
