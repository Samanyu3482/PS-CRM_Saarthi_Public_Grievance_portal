import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from app.db.database import Base

class UserDB(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    firebase_uid = Column(String, unique=True, index=True, nullable=True)
    auth0_id = Column(String, unique=True, index=True, nullable=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=True)
    role = Column(String, nullable=False)
    password_hash = Column(String, nullable=True)
    
    # Polymorphic / Role-specific fields (nullable)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    state = Column(String, nullable=True)
    pincode = Column(String, nullable=True)
    department = Column(String, nullable=True)
    employee_id = Column(String, nullable=True)
    ministry_name = Column(String, nullable=True)
    designation = Column(String, nullable=True)
    constituency = Column(String, nullable=True)
    party_name = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        d = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        # Map Postgres "id" to MongoDB "_id" compatibility field
        d["_id"] = self.id
        if isinstance(d.get("created_at"), datetime):
            d["created_at"] = d["created_at"].isoformat()
        return d

class ComplaintDB(Base):
    __tablename__ = "complaints"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    category = Column(String, nullable=True)
    location = Column(JSONB, nullable=False)  # stores address, city, state, pincode, coordinates
    images = Column(JSONB, default=list)      # list of string URLs
    created_by = Column(String, nullable=False)
    status = Column(String, default="submitted")
    priority = Column(String, default="medium")
    assigned_to = Column(String, nullable=True)
    ministry = Column(String, nullable=True)
    department = Column(String, nullable=True)
    sub_department = Column(String, nullable=True)
    duplicate_of = Column(String, nullable=True)
    sentiment_score = Column(Float, nullable=True)
    sla_deadline = Column(DateTime(timezone=True), nullable=True)
    feedback = Column(JSONB, nullable=True)
    embedding = Column(JSONB, nullable=True)
    notes = Column(JSONB, default=list)
    is_spam = Column(Boolean, default=False)
    spam_matched_on = Column(JSONB, default=list)
    spam_reason = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        d = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        d["_id"] = self.id
        return d

class DepartmentDB(Base):
    __tablename__ = "departments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ministry = Column(String, nullable=False)
    department = Column(String, nullable=False)
    sub_departments = Column(JSONB, default=list)

    def to_dict(self):
        d = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        d["_id"] = self.id
        return d

class OfficerDB(Base):
    __tablename__ = "officers"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    ministry = Column(String, nullable=False)
    department = Column(String, nullable=False)
    sub_department = Column(String, nullable=True)
    city = Column(String, nullable=False)
    state = Column(String, nullable=False)
    employee_id = Column(String, nullable=False)
    current_workload = Column(Integer, default=0)

    def to_dict(self):
        d = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        d["_id"] = self.id
        return d

class NotificationDB(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)
    type = Column(String, nullable=False)
    is_read = Column(Boolean, default=False)
    reference_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        d = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        d["_id"] = self.id
        return d

class WhatsAppSessionDB(Base):
    __tablename__ = "whatsapp_sessions"

    phone = Column(String, primary_key=True)
    messages = Column(JSONB, default=list)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "phone": self.phone,
            "messages": self.messages,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class BlacklistedTokenDB(Base):
    __tablename__ = "blacklisted_tokens"

    hashed_token = Column(String, primary_key=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
