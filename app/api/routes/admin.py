from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from typing import Optional
from pydantic import BaseModel, EmailStr
from app.db.mongodb import db_client
from app.schemas.user import RoleEnum, UserInDB
from bson import ObjectId

router = APIRouter(prefix="/admin", tags=["admin"])


# ── helpers ──────────────────────────────────────────────────────────────────

async def require_admin(request: Request):
    """Dependency: reads session cookie and verifies user is admin.
    Supports auth0_id, firebase_uid, email, and _id lookups."""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    
    raw = None
    # Try auth0_id first
    raw = await db_client.db["users"].find_one({"auth0_id": token})
    # Try firebase_uid
    if not raw:
        raw = await db_client.db["users"].find_one({"firebase_uid": token})
    # Try by ObjectId (_id)
    if not raw:
        try:
            raw = await db_client.db["users"].find_one({"_id": ObjectId(token)})
        except Exception:
            pass
    # Try by email (for dev-login or email-based tokens)
    if not raw and "@" in token:
        raw = await db_client.db["users"].find_one({"email": token})
    
    if not raw or raw.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return raw


def _serialize(doc: dict) -> dict:
    doc["_id"] = str(doc["_id"])
    doc.setdefault("auth0_id", doc["_id"])
    doc.setdefault("name", "")
    doc.setdefault("phone", "")
    doc.setdefault("role", "citizen")
    return doc


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
    pipeline = [{"$group": {"_id": "$role", "count": {"$sum": 1}}}]
    cursor = db_client.db["users"].aggregate(pipeline)
    results = await cursor.to_list(length=100)
    stats = {r["_id"]: r["count"] for r in results if r["_id"]}
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
    total = await db_client.db["complaints"].count_documents({})
    resolved = await db_client.db["complaints"].count_documents({"status": "resolved"})
    pending = await db_client.db["complaints"].count_documents({"status": {"$in": ["submitted", "classified", "assigned", "in_progress"]}})
    
    return {
        "total_complaints": total,
        "resolved_complaints": resolved,
        "pending_complaints": pending,
        "resolution_rate": round(resolved / total * 100, 2) if total > 0 else 0
    }


@router.get("/department-feedback")
async def get_department_feedback(_admin=Depends(require_admin)):
    """Return average feedback ratings aggregated by department."""
    pipeline = [
        {"$match": {"feedback.rating": {"$exists": True}}},
        {"$group": {
            "_id": {"$ifNull": ["$department", "Unknown Department"]},
            "average_rating": {"$avg": "$feedback.rating"},
            "total_feedbacks": {"$sum": 1}
        }},
        {"$sort": {"average_rating": -1}}
    ]
    cursor = db_client.db["complaints"].aggregate(pipeline)
    results = await cursor.to_list(length=200)
    
    return [
        {
            "department": r["_id"],
            "average_rating": round(r["average_rating"], 1),
            "total_feedbacks": r["total_feedbacks"]
        }
        for r in results
    ]


@router.get("/recent-complaints")
async def get_recent_complaints(_admin=Depends(require_admin)):
    """Return 10 most recent complaints."""
    cursor = db_client.db["complaints"].find().sort("created_at", -1).limit(10)
    complaints = await cursor.to_list(length=10)
    for c in complaints:
        c["_id"] = str(c["_id"])
        # Ensure created_at is serialized
        if "created_at" in c and c["created_at"]:
             if hasattr(c["created_at"], "isoformat"):
                 c["created_at"] = c["created_at"].isoformat()
             else:
                 c["created_at"] = str(c["created_at"])
    return complaints


@router.get("/recent-users")
async def get_recent_users(_admin=Depends(require_admin)):
    """Return 10 most recent users."""
    cursor = db_client.db["users"].find().sort("_id", -1).limit(10)
    users = await cursor.to_list(length=100)
    for u in users:
        u["_id"] = str(u["_id"])
    return users


@router.get("/users")
async def list_users(role: Optional[str] = None, _admin=Depends(require_admin)):
    """List all users, optionally filtered by role."""
    query = {}
    if role:
        query["role"] = role
    cursor = db_client.db["users"].find(query)
    users = await cursor.to_list(length=500)
    return [_serialize(u) for u in users]


@router.post("/users", status_code=201)
async def create_user(body: AdminUserCreate, _admin=Depends(require_admin)):
    """Create a new user directly (no Firebase required for officials)."""
    existing = await db_client.db["users"].find_one({"email": body.email})
    if existing:
        raise HTTPException(status_code=400, detail="A user with this email already exists")

    user_dict = body.model_dump(exclude_none=True)
    # Use email as a synthetic auth0_id for admin-created users
    user_dict["auth0_id"] = f"admin_created_{body.email}"
    result = await db_client.db["users"].insert_one(user_dict)
    created = await db_client.db["users"].find_one({"_id": result.inserted_id})
    return _serialize(created)


@router.delete("/users/{user_id}", status_code=200)
async def delete_user(user_id: str, _admin=Depends(require_admin)):
    """Delete a user by MongoDB _id."""
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    result = await db_client.db["users"].delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted successfully"}
