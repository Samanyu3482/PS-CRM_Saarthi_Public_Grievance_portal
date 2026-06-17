from app.db.database import get_db_ctx
from app.db.models import NotificationDB
from app.schemas.notification import NotificationInDB
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import select

async def create_notification(user_id: str, message: str) -> NotificationInDB:
    db_notification = NotificationDB(
        user_id=user_id,
        title="Notification",
        message=message,
        type="system",
        is_read=False,
        created_at=datetime.now(timezone.utc)
    )
    
    async with get_db_ctx() as session:
        session.add(db_notification)
        await session.commit()
        await session.refresh(db_notification)
        data = db_notification.to_dict()
        
    return NotificationInDB(**data)

async def get_user_notifications(user_id: str, skip: int = 0, limit: int = 50) -> List[NotificationInDB]:
    async with get_db_ctx() as session:
        stmt = (
            select(NotificationDB)
            .where(NotificationDB.user_id == user_id)
            .order_by(NotificationDB.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(stmt)
        notifications = result.scalars().all()
        return [NotificationInDB(**n.to_dict()) for n in notifications]

async def mark_as_read(notification_id: str) -> Optional[NotificationInDB]:
    async with get_db_ctx() as session:
        stmt = select(NotificationDB).where(NotificationDB.id == notification_id)
        result = await session.execute(stmt)
        n = result.scalar_one_or_none()
        if n:
            n.is_read = True
            session.add(n)
            await session.commit()
            return NotificationInDB(**n.to_dict())
    return None
