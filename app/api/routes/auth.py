from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from app.schemas.user import UserCreate, UserInDB
from app.services import user_service
from app.api.deps import get_current_user

from app.core.config import settings

from pydantic import BaseModel
import httpx
import json


class DevLogin(BaseModel):
    email: str
    password: str | None = None


class FirebaseLogin(BaseModel):
    idToken: str


router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/signup", response_model=UserInDB)
async def signup(user_in: UserCreate):
    existing_user = await user_service.get_user_by_firebase_uid(user_in.firebase_uid)
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





@router.post("/dev-login", response_model=UserInDB)
async def dev_login(body: DevLogin, response: Response):
    """Development-only login: lookup user by email and set a simple dev session cookie containing auth0_id."""
    user = await user_service.get_user_by_email(body.email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    response.set_cookie(
        key="access_token",
        value=user.firebase_uid,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=3600,
    )
    return user


@router.post("/logout")
async def logout(request: Request, response: Response):
    # Try to blacklist token if present in cookie
    token = None
    token = request.cookies.get("access_token")
    if token:
        await user_service.blacklist_token(token)

    # Clear cookie
    response.delete_cookie("access_token")
    return {"message": "Successfully logged out"}


@router.post("/firebase-login", response_model=UserInDB)
async def firebase_login(body: FirebaseLogin, response: Response):
    """
    Backend Firebase authentication endpoint.
    Verifies Firebase ID token and sets session cookie if user exists in MongoDB.
    """
    try:
        # Verify Firebase ID token using Firebase REST API
        verification_url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={settings.FIREBASE_API_KEY}"
        
        async with httpx.AsyncClient() as client:
            verify_response = await client.post(
                verification_url,
                json={"idToken": body.idToken}
            )
        
        if verify_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Firebase token"
            )
        
        token_data = verify_response.json()
        if "users" not in token_data or len(token_data["users"]) == 0:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found in Firebase")
        
        user_info = token_data["users"][0]
        email = user_info.get("email")
        uid = user_info.get("localId")
        
        # Check if user exists in our database
        user = await user_service.get_user_by_firebase_uid(uid)
        if not user:
            # Check by email as fallback
            user = await user_service.get_user_by_email(email)
            
        if not user:
            # Return specific error so frontend knows to call /signup
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="User not found in our records. Please complete signup."
            )
        
        # Set HttpOnly cookie with Firebase UID
        response.set_cookie(
            key="access_token",
            value=uid,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=3600*24, # 1 day
        )
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class OfficialLogin(BaseModel):
    email: str
    password: str # In real app, verify against hash. For now, simple check.

@router.post("/official-login", response_model=UserInDB)
async def official_login(body: OfficialLogin, response: Response):
    """
    Login endpoint for government officials.
    """
    user = await user_service.get_user_by_email(body.email)
    if not user or user.role == "citizen":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid official credentials or unauthorized role"
        )
    
    # In a real app, we'd verify the password hash here.
    # For now, we allow login if the official exists in DB.
    
    response.set_cookie(
        key="access_token",
        value=user.firebase_uid,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=3600*24,
    )
    return user
