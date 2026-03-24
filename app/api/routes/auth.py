from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from app.schemas.user import UserCreate, UserInDB, UserSignupRequest
from app.services import user_service
from app.api.deps import get_current_user
from app.core.security import decode_jwt
from app.core.config import settings

from pydantic import BaseModel
import httpx
import json


class FirebaseLogin(BaseModel):
    idToken: str

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenBody(BaseModel):
    token: str

class DevLogin(BaseModel):
    email: str

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/signup", response_model=UserInDB)
async def signup(signup_req: UserSignupRequest):
    user_data = signup_req.user_data
    
    # Check if user already exists in DB
    existing_user = await user_service.get_user_by_email(user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists in our system. Please log in."
        )
    
    uid = None
    
    # Priority 1: Use id_token if provided (Social Login)
    if signup_req.id_token:
        lookup_url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={settings.FIREBASE_API_KEY}"
        async with httpx.AsyncClient() as client:
            lookup_res = await client.post(lookup_url, json={"idToken": signup_req.id_token})
        
        if lookup_res.status_code == 200:
            token_data = lookup_res.json()
            if "users" in token_data and len(token_data["users"]) > 0:
                uid = token_data["users"][0].get("localId")
                email = token_data["users"][0].get("email")
                if email != user_data.email:
                    raise HTTPException(status_code=400, detail="Token email does not match form email")
            else:
                raise HTTPException(status_code=400, detail="Invalid token - user not found")
        else:
            raise HTTPException(status_code=lookup_res.status_code, detail="Social token verification failed")
            
    # Priority 2: Use password for Email/Password Signup
    elif signup_req.password:
        signup_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={settings.FIREBASE_API_KEY}"
        async with httpx.AsyncClient() as client:
            fb_res = await client.post(
                signup_url,
                json={
                    "email": user_data.email,
                    "password": signup_req.password,
                    "returnSecureToken": True
                }
            )
        
        if fb_res.status_code == 200:
            uid = fb_res.json().get("localId")
        elif fb_res.status_code == 400:
            error_msg = fb_res.json().get("error", {}).get("message")
            if error_msg == "EMAIL_EXISTS":
                # User exists in Firebase, verify their password to get UID
                login_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={settings.FIREBASE_API_KEY}"
                async with httpx.AsyncClient() as client:
                    login_res = await client.post(
                        login_url,
                        json={
                            "email": user_data.email,
                            "password": signup_req.password,
                            "returnSecureToken": True
                        }
                    )
                if login_res.status_code == 200:
                    uid = login_res.json().get("localId")
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST, 
                        detail="Account already exists in Firebase but password verification failed."
                    )
            else:
                raise HTTPException(status_code=400, detail=error_msg)
        else:
            raise HTTPException(status_code=fb_res.status_code, detail="Firebase communication error")
    else:
        raise HTTPException(status_code=400, detail="Either password or id_token must be provided")
    
    # 3. Create user in MongoDB
    user_data.auth0_id = uid
    return await user_service.create_user(user_data)

@router.get("/me", response_model=UserInDB)
async def get_my_profile(current_user: UserInDB = Depends(get_current_user)):
    return current_user

@router.post("/login", response_model=UserInDB)
async def login(body: LoginRequest, response: Response):
    """
    Unified login endpoint that verifies credentials with Firebase
    and sets a session cookie.
    """
    # 1. Verify credentials with Firebase REST API
    login_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={settings.FIREBASE_API_KEY}"
    async with httpx.AsyncClient() as client:
        fb_res = await client.post(
            login_url,
            json={
                "email": body.email,
                "password": body.password,
                "returnSecureToken": True
            }
        )
    
    if fb_res.status_code != 200:
        detail = fb_res.json().get("error", {}).get("message", "Invalid credentials")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)
    
    fb_data = fb_res.json()
    uid = fb_data.get("localId")
    
    # 2. Get user from DB
    user = await user_service.get_user_by_auth0_id(uid)
    if not user:
        # Fallback to email
        user = await user_service.get_user_by_email(body.email)
    
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in system")
    
    # 3. Set session cookie
    response.set_cookie(
        key="access_token",
        value=uid,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=3600*24,
    )
    return user



@router.post("/session", response_model=UserInDB)
async def create_session(body: TokenBody, response: Response):
    """Create a server-side HttpOnly session cookie from a client-provided JWT token (Auth0).
    Client should POST { token: '<id_token>' } after a successful Auth0 login.
    """
    payload = decode_jwt(body.token)
    auth0_id = payload.get("sub")
    if not auth0_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token payload")

    user = await user_service.get_user_by_auth0_id(auth0_id)
    if not user:
        # User needs to finish signup in our system
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found - please sign up")

    # Set HttpOnly cookie
    response.set_cookie(
        key="access_token",
        value=body.token,
        httponly=True,
        secure=False,  # set True in production (HTTPS)
        samesite="lax",
        max_age=3600,
    )
    return user


@router.post("/dev-login", response_model=UserInDB)
async def dev_login(body: DevLogin, response: Response):
    """Development-only login: lookup user by email and set a simple dev session cookie containing auth0_id."""
    user = await user_service.get_user_by_email(body.email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    response.set_cookie(
        key="access_token",
        value=user.auth0_id,
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
        user = await user_service.get_user_by_auth0_id(uid)
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
        value=user.auth0_id,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=3600*24,
    )
    return user
