from fastapi import Depends, HTTPException, status, Request
from app.core.security import verify_token, verify_token_from_cookie
from app.db.database import get_db_ctx
from app.db.models import UserDB
from app.schemas.user import UserInDB, RoleEnum
from sqlalchemy import select

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
    
    async with get_db_ctx() as session:
        # Check by firebase_uid
        stmt = select(UserDB).where(UserDB.firebase_uid == firebase_uid)
        result = await session.execute(stmt)
        user_model = result.scalar_one_or_none()
        
        if not user_model:
            # Check by auth0_id
            stmt = select(UserDB).where(UserDB.auth0_id == firebase_uid)
            result = await session.execute(stmt)
            user_model = result.scalar_one_or_none()
            
        if not user_model:
            # Check by id (primary key)
            stmt = select(UserDB).where(UserDB.id == firebase_uid)
            result = await session.execute(stmt)
            user_model = result.scalar_one_or_none()
            
        if not user_model and "@" in firebase_uid:
            # Check by email
            stmt = select(UserDB).where(UserDB.email == firebase_uid)
            result = await session.execute(stmt)
            user_model = result.scalar_one_or_none()
            
        if not user_model:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
            
        user_doc = user_model.to_dict()
        
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
