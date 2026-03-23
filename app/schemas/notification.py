from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone

class NotificationInDB(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    message: str
    is_read: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
