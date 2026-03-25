from fastapi import Depends, HTTPException, status, Request
from app.core.security import verify_token, verify_token_from_cookie
from app.db.mongodb import db_client
from app.schemas.user import UserInDB, RoleEnum
from app.services.user_service import is_token_blacklisted

async def get_current_user(request: Request, token_payload: dict | None = Depends(verify_token)) -> UserInDB:
    # Try Authorization header first; if not present, attempt cookie-based session
    if token_payload is None:
        try:
            token_payload = verify_token_from_cookie(request)
        except HTTPException:
            token_payload = None

    if not token_payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid token")

    raw_token = token_payload.get("_raw_token")
    if raw_token and await is_token_blacklisted(raw_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been logged out")

    firebase_uid = token_payload.get("sub")
    if not firebase_uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    
    user_doc = await db_client.db["users"].find_one({"firebase_uid": firebase_uid})
    if not user_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    if "_id" in user_doc:
        user_doc["_id"] = str(user_doc["_id"])
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
