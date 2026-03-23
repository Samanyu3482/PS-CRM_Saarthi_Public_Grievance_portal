from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.schemas.user import UserInDB
from app.schemas.notification import NotificationInDB
from app.api.deps import get_current_user
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("/", response_model=List[NotificationInDB])
async def get_my_notifications(
    current_user: UserInDB = Depends(get_current_user),
    skip: int = 0,
    limit: int = 50
):
    """
    Get all notifications for the logged-in user.
    """
    return await notification_service.get_user_notifications(current_user.auth0_id, skip=skip, limit=limit)

@router.patch("/{notification_id}/read", response_model=NotificationInDB)
async def mark_notification_read(
    notification_id: str,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Mark a specific notification as read.
    """
    updated = await notification_service.mark_as_read(notification_id)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
        
    # Security check - ensure the notification belongs to current user
    if updated.user_id != current_user.auth0_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        
    return updated
