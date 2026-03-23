from pydantic import BaseModel, Field, conint
from typing import Optional, List
from datetime import datetime, timezone
from enum import Enum

class ComplaintStatus(str, Enum):
    submitted = "submitted"
    classified = "classified"
    assigned = "assigned"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"

class PriorityEnum(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"

class Coordinates(BaseModel):
    lat: Optional[float] = None
    lng: Optional[float] = None

class Location(BaseModel):
    address: str
    city: str
    state: str
    pincode: str
    coordinates: Optional[Coordinates] = None

class Feedback(BaseModel):
    rating: conint(ge=1, le=5) # type: ignore
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Note(BaseModel):
    user_id: str
    text: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ComplaintCreate(BaseModel):
    title: str
    description: str
    address: str
    city: str
    state: str
    pincode: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    images: Optional[List[str]] = []

class ComplaintUpdate(BaseModel):
    status: Optional[ComplaintStatus] = None
    priority: Optional[PriorityEnum] = None
    assigned_to: Optional[str] = None
    department: Optional[str] = None
    duplicate_of: Optional[str] = None
    category: Optional[str] = None
    sentiment_score: Optional[float] = None
    sla_deadline: Optional[datetime] = None
    feedback: Optional[Feedback] = None
    notes: Optional[List[Note]] = None

class ComplaintInDB(BaseModel):
    id: str = Field(alias="_id")
    title: str
    description: str
    category: Optional[str] = None
    location: Location
    images: List[str] = []
    created_by: str
    status: ComplaintStatus = ComplaintStatus.submitted
    priority: PriorityEnum = PriorityEnum.medium
    assigned_to: Optional[str] = None
    department: Optional[str] = None
    duplicate_of: Optional[str] = None
    sentiment_score: Optional[float] = None
    sla_deadline: Optional[datetime] = None
    feedback: Optional[Feedback] = None
    notes: List[Note] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
