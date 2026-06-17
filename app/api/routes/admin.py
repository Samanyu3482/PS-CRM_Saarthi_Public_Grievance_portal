from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from pydantic import BaseModel, EmailStr
from app.db.database import get_db_ctx
from app.db.models import UserDB, ComplaintDB
from app.schemas.user import RoleEnum, UserInDB
from app.api.deps import get_current_user
from sqlalchemy import select, func, Float
from datetime import datetime

router = APIRouter(prefix="/admin", tags=["admin"])

async def require_admin(current_user: UserInDB = Depends(get_current_user)):
    """Dependency: verifies the caller is authenticated and has admin role."""
    if current_user.role != RoleEnum.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user

# ── schemas ───────────────────────────────────────────────────────────────────

class AdminUserCreate(BaseModel):
    email: EmailStr
    name: str
    phone: str = ""
    role: RoleEnum
    # officer fields
    department: Optional[str] = None
    city: Optional[str] = None
    employee_id: Optional[str] = None
    # mp_mla fields
    constituency: Optional[str] = None
    state: Optional[str] = None
    party_name: Optional[str] = None
    # ministry fields
    ministry_name: Optional[str] = None
    designation: Optional[str] = None
    # citizen fields
    address: Optional[str] = None
    pincode: Optional[str] = None

# ── routes ────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats(_admin=Depends(require_admin)):
    """Return per-role user counts."""
    async with get_db_ctx() as session:
        stmt = select(UserDB.role, func.count()).group_by(UserDB.role)
        result = await session.execute(stmt)
        stats = {row[0]: row[1] for row in result.all() if row[0]}
        
    return {
        "citizen": stats.get("citizen", 0),
        "officer": stats.get("officer", 0),
        "mc": stats.get("mc", 0),
        "mp_mla": stats.get("mp_mla", 0),
        "ministry": stats.get("ministry", 0),
        "admin": stats.get("admin", 0),
        "total": sum(stats.values()),
    }

@router.get("/platform-stats")
async def get_platform_stats(_admin=Depends(require_admin)):
    """Return platform-wide complaint statistics."""
    async with get_db_ctx() as session:
        total = (await session.execute(select(func.count(ComplaintDB.id)))).scalar() or 0
        resolved = (await session.execute(select(func.count(ComplaintDB.id)).where(ComplaintDB.status == "resolved"))).scalar() or 0
        pending = (await session.execute(select(func.count(ComplaintDB.id)).where(ComplaintDB.status.in_(["submitted", "classified", "assigned", "in_progress"])))).scalar() or 0
    
    return {
        "total_complaints": total,
        "resolved_complaints": resolved,
        "pending_complaints": pending,
        "resolution_rate": round(resolved / total * 100, 2) if total > 0 else 0
    }

@router.get("/department-feedback")
async def get_department_feedback(_admin=Depends(require_admin)):
    """Return average feedback ratings aggregated by department."""
    rating_expr = func.cast(func.jsonb_extract_path_text(ComplaintDB.feedback, 'rating'), Float)
    async with get_db_ctx() as session:
        stmt = (
            select(
                ComplaintDB.department.label("department"),
                func.avg(rating_expr).label("average_rating"),
                func.count(rating_expr).label("total_feedbacks")
            )
            .where(func.jsonb_extract_path_text(ComplaintDB.feedback, 'rating').isnot(None))
            .group_by(ComplaintDB.department)
            .order_by(func.avg(rating_expr).desc())
        )
        rows = (await session.execute(stmt)).all()
    
    return [
        {
            "department": row.department or "Unknown Department",
            "average_rating": round(float(row.average_rating or 0.0), 1),
            "total_feedbacks": int(row.total_feedbacks or 0)
        }
        for row in rows
    ]

@router.get("/recent-complaints")
async def get_recent_complaints(_admin=Depends(require_admin)):
    """Return 10 most recent complaints."""
    async with get_db_ctx() as session:
        stmt = select(ComplaintDB).order_by(ComplaintDB.created_at.desc()).limit(10)
        result = await session.execute(stmt)
        complaints = [c.to_dict() for c in result.scalars().all()]
        
    for c in complaints:
        if isinstance(c.get("created_at"), datetime):
            c["created_at"] = c["created_at"].isoformat()
    return complaints

@router.get("/recent-users")
async def get_recent_users(_admin=Depends(require_admin)):
    """Return 10 most recent users."""
    async with get_db_ctx() as session:
        stmt = select(UserDB).order_by(UserDB.created_at.desc()).limit(10)
        result = await session.execute(stmt)
        users = [u.to_dict() for u in result.scalars().all()]
    return users

@router.get("/users")
async def list_users(role: Optional[str] = None, _admin=Depends(require_admin)):
    """List all users, optionally filtered by role."""
    async with get_db_ctx() as session:
        stmt = select(UserDB)
        if role:
            stmt = stmt.where(UserDB.role == role)
        result = await session.execute(stmt)
        users = [u.to_dict() for u in result.scalars().all()]
    return users

@router.post("/users", status_code=201)
async def create_user(body: AdminUserCreate, _admin=Depends(require_admin)):
    """Create a new user directly (no Firebase required for officials)."""
    async with get_db_ctx() as session:
        stmt = select(UserDB).where(UserDB.email == body.email)
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="A user with this email already exists")

        db_user = UserDB(
            email=body.email,
            name=body.name,
            phone=body.phone,
            role=body.role.value if hasattr(body.role, "value") else body.role,
            auth0_id=f"admin_created_{body.email}",
            # officer
            department=body.department,
            city=body.city,
            employee_id=body.employee_id,
            # mp_mla
            constituency=body.constituency,
            state=body.state,
            party_name=body.party_name,
            # ministry
            ministry_name=body.ministry_name,
            designation=body.designation,
            # citizen
            address=body.address,
            pincode=body.pincode
        )
        session.add(db_user)
        await session.commit()
        await session.refresh(db_user)
        return db_user.to_dict()

@router.delete("/users/{user_id}", status_code=200)
async def delete_user(user_id: str, _admin=Depends(require_admin)):
    """Delete a user by primary key id."""
    async with get_db_ctx() as session:
        stmt = select(UserDB).where(UserDB.id == user_id)
        result = await session.execute(stmt)
        u = result.scalar_one_or_none()
        if not u:
            raise HTTPException(status_code=404, detail="User not found")
        await session.delete(u)
        await session.commit()
    return {"message": "User deleted successfully"}
