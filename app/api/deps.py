from fastapi import Depends, HTTPException, status
from app.core.security import verify_token
from app.db.mongodb import db_client
from app.schemas.user import UserInDB, RoleEnum
from app.services.user_service import is_token_blacklisted

async def get_current_user(token_payload: dict = Depends(verify_token)) -> UserInDB:
    raw_token = token_payload.get("_raw_token")
    if raw_token and await is_token_blacklisted(raw_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been logged out")

    auth0_id = token_payload.get("sub")
    if not auth0_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    
    user_doc = await db_client.db["users"].find_one({"auth0_id": auth0_id})
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
