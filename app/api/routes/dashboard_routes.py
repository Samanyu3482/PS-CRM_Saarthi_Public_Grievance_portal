from fastapi import APIRouter, Depends, Query
from app.schemas.user import UserInDB, RoleEnum
from app.api.deps import RoleChecker
from app.services import dashboard_service

router = APIRouter(tags=["dashboard"])

def get_user_field(user: UserInDB, field_name: str, default: str) -> str:
    # First try direct attribute
    val = getattr(user, field_name, None)
    if val: return val
    # Then check model_extra if dynamic Pydantic fields are absorbed there
    if hasattr(user, 'model_extra') and user.model_extra and field_name in user.model_extra:
        return user.model_extra[field_name]
    return default

@router.get("/dashboard/citizen")
async def citizen_dash(current_user: UserInDB = Depends(RoleChecker([RoleEnum.citizen]))):
    return await dashboard_service.get_citizen_dashboard(current_user.auth0_id)

@router.get("/dashboard/officer")
async def officer_dash(current_user: UserInDB = Depends(RoleChecker([RoleEnum.officer]))):
    dept = get_user_field(current_user, 'department', 'Public Works Department (PWD)')
    return await dashboard_service.get_officer_dashboard(dept)

@router.get("/officer/performance")
async def officer_perf(current_user: UserInDB = Depends(RoleChecker([RoleEnum.officer]))):
    dept = get_user_field(current_user, 'department', 'Public Works Department (PWD)')
    return await dashboard_service.get_officer_performance(dept)

@router.get("/dashboard/region")
async def region_dash(
    constituency: str = Query(None, description="Provide constituency to filter"),
    state: str = Query(None, description="Provide state to filter"),
    current_user: UserInDB = Depends(RoleChecker([RoleEnum.mp_mla]))
):
    valid_state = state or get_user_field(current_user, 'state', 'Delhi')
    valid_city = constituency  # Assuming constituency maps to city in MVP schema
    return await dashboard_service.get_region_dashboard(state=valid_state, city=valid_city)

@router.get("/dashboard/admin")
async def admin_dash(current_user: UserInDB = Depends(RoleChecker([RoleEnum.ministry]))):
    # Ministry essentially acts as Admin for the system.
    return await dashboard_service.get_admin_dashboard()
