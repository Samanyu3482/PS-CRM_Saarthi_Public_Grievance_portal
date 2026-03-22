from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.schemas.user import UserInDB, RoleEnum
from app.schemas.complaint import ComplaintCreate, ComplaintInDB, ComplaintUpdate
from app.api.deps import get_current_user, RoleChecker
from app.services import complaint_service

router = APIRouter(prefix="/complaints", tags=["complaints"])

@router.post("/", response_model=ComplaintInDB, status_code=status.HTTP_201_CREATED)
async def create_complaint(
    complaint_in: ComplaintCreate,
    current_user: UserInDB = Depends(RoleChecker([RoleEnum.citizen]))
):
    """
    Submit a new complaint. Only accessible by Citizens.
    """
    return await complaint_service.create_complaint(complaint_in, user_auth0_id=current_user.auth0_id)

@router.get("/my", response_model=List[ComplaintInDB])
async def get_my_complaints(
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Get all complaints created by the logged-in user.
    """
    return await complaint_service.get_user_complaints(current_user.auth0_id)

@router.get("/{complaint_id}", response_model=ComplaintInDB)
async def get_complaint(
    complaint_id: str,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Get specific complaint details.
    """
    complaint = await complaint_service.get_complaint_by_id(complaint_id)
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")
        
    # Security: A citizen can only view their own complaints. 
    # Officers/Ministry/MP_MLA can view any complaint based on requirements.
    if current_user.role == RoleEnum.citizen and complaint.created_by != current_user.auth0_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this complaint")
        
    return complaint

@router.patch("/{complaint_id}/status", response_model=ComplaintInDB)
async def update_complaint_status(
    complaint_id: str,
    update_data: ComplaintUpdate,
    current_user: UserInDB = Depends(RoleChecker([RoleEnum.officer, RoleEnum.ministry]))
):
    """
    Update complaint details (assign, resolve, duplicate_of, sentiment_score, etc.).
    Only Officers and Ministry officials can update complaints.
    """
    complaint = await complaint_service.get_complaint_by_id(complaint_id)
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")
        
    updated = await complaint_service.update_complaint(complaint_id, update_data)
    return updated
