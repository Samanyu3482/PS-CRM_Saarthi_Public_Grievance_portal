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
    return await complaint_service.create_complaint(complaint_in, user_firebase_uid=current_user.firebase_uid)

@router.get("/my", response_model=List[ComplaintInDB])
async def get_my_complaints(
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Get all complaints created by the logged-in user.
    """
    return await complaint_service.get_user_complaints(current_user.firebase_uid)

@router.get("/assigned", response_model=List[ComplaintInDB])
async def get_assigned_complaints(
    current_user: UserInDB = Depends(RoleChecker([RoleEnum.officer])),
    skip: int = 0,
    limit: int = 50
):
    """
    Get all complaints assigned to the logged-in officer.
    """
    return await complaint_service.get_assigned_complaints(current_user.firebase_uid, skip=skip, limit=limit)


@router.get("/spam", response_model=List[ComplaintInDB])
async def get_spam_complaints(
    current_user: UserInDB = Depends(RoleChecker([RoleEnum.officer, RoleEnum.ministry])),
    skip: int = 0,
    limit: int = 50
):
    """
    Get all spam-flagged complaints for officer/ministry review.
    """
    return await complaint_service.get_flagged_spam_complaints(skip=skip, limit=limit)


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
    if current_user.role == RoleEnum.citizen and complaint.created_by != current_user.firebase_uid:
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

from pydantic import BaseModel
class FeedbackCreate(BaseModel):
    rating: int
    comment: str | None = None

@router.post("/{complaint_id}/feedback", response_model=ComplaintInDB)
async def submit_feedback(
    complaint_id: str,
    feedback_in: FeedbackCreate,
    current_user: UserInDB = Depends(RoleChecker([RoleEnum.citizen]))
):
    """
    Submit feedback/rating for a resolved complaint. Only accessible by Citizens.
    """
    complaint = await complaint_service.get_complaint_by_id(complaint_id)
    if not complaint or complaint.created_by != current_user.firebase_uid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found or not authorized")
        
    updated = await complaint_service.add_feedback(complaint_id, feedback_in.rating, feedback_in.comment)
    if not updated:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to add feedback")
    return updated

class NoteCreate(BaseModel):
    text: str

@router.post("/{complaint_id}/notes", response_model=ComplaintInDB)
async def add_note(
    complaint_id: str,
    note_in: NoteCreate,
    current_user: UserInDB = Depends(RoleChecker([RoleEnum.officer, RoleEnum.ministry]))
):
    """
    Add an internal note to a complaint. Only accessible by Officers and Ministry.
    """
    complaint = await complaint_service.get_complaint_by_id(complaint_id)
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")
        
    updated = await complaint_service.add_note(complaint_id, current_user.firebase_uid, note_in.text)
    if not updated:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to add note")
    return updated
