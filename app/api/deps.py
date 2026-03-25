from fastapi import Depends, HTTPException, status, Request
from app.core.security import verify_token, verify_token_from_cookie
from app.db.mongodb import db_client
from app.schemas.user import UserInDB, RoleEnum
from app.services.user_service import is_token_blacklisted
from bson import ObjectId

async def get_current_user(request: Request, token_payload: dict | None = Depends(verify_token)) -> UserInDB:
    # Try Authorization header first; if not present, attempt cookie-based session
    if token_payload is None:
        try:
            token_payload = verify_token_from_cookie(request)
        except HTTPException:
            token_payload = None

    if not token_payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid token")

    firebase_uid = token_payload.get("sub")
    if not firebase_uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    
    # Try multiple lookup strategies to find the user
    user_doc = await db_client.db["users"].find_one({"firebase_uid": firebase_uid})
    if not user_doc:
        user_doc = await db_client.db["users"].find_one({"auth0_id": firebase_uid})
    if not user_doc:
        try:
            user_doc = await db_client.db["users"].find_one({"_id": ObjectId(firebase_uid)})
        except Exception:
            pass
    if not user_doc and "@" in firebase_uid:
        user_doc = await db_client.db["users"].find_one({"email": firebase_uid})
    
    if not user_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    if "_id" in user_doc:
        user_doc["_id"] = str(user_doc["_id"])
    # Provide defaults for fields UserInDB requires
    user_doc.setdefault("firebase_uid", str(user_doc["_id"]))
    user_doc.setdefault("name", "")
    user_doc.setdefault("phone", "")
    return UserInDB(**user_doc)

class RoleChecker:
    def __init__(self, allowed_roles: list[RoleEnum]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: UserInDB = Depends(get_current_user)):
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted"
            )
        return user
