from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.user import UserCreate, UserInDB
from app.services import user_service
from app.api.deps import get_current_user, verify_token

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/signup", response_model=UserInDB)
async def signup(user_in: UserCreate):
    existing_user = await user_service.get_user_by_auth0_id(user_in.auth0_id)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists"
        )
    return await user_service.create_user(user_in)

@router.get("/me", response_model=UserInDB)
async def get_my_profile(current_user: UserInDB = Depends(get_current_user)):
    return current_user

@router.post("/login", response_model=UserInDB)
async def login(current_user: UserInDB = Depends(get_current_user)):
    """
    Since Auth0 handles the credentials, sign in only requires the JWT Bearer token
    passed in the Authorization header. It dynamically returns the role-specific profile!
    """
    return current_user

@router.post("/logout")
async def logout(token_payload: dict = Depends(verify_token)):
    """
    Adds the current JWT token to a blacklist database to invalidate it backend-side.
    """
    raw_token = token_payload.get("_raw_token")
    if raw_token:
        await user_service.blacklist_token(raw_token)
    return {"message": "Successfully logged out"}
