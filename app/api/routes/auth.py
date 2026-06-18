from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from pydantic import BaseModel
import httpx
import bcrypt
from sqlalchemy import select

from app.schemas.user import UserCreate, UserInDB, UserSignupRequest
from app.services import user_service
from app.api.deps import get_current_user
from app.core.config import settings
from app.db.database import get_db_ctx
from app.db.models import UserDB


router = APIRouter(prefix="/auth", tags=["auth"])


class FirebaseLogin(BaseModel):
    idToken: str


class LoginRequest(BaseModel):
    email: str
    password: str


class OfficialLogin(BaseModel):
    email: str
    password: str


# ── Citizen Signup ──────────────────────────────────────────────────────────

@router.post("/signup", response_model=UserInDB)
async def signup(signup_req: UserSignupRequest):
    user_data = signup_req.user_data

    if await user_service.get_user_by_email(user_data.email):
        raise HTTPException(status_code=400, detail="User already exists. Please log in.")

    uid = None

    if signup_req.id_token:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={settings.FIREBASE_API_KEY}",
                json={"idToken": signup_req.id_token},
            )
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail="Social token verification failed")
        users = res.json().get("users", [])
        if not users:
            raise HTTPException(status_code=400, detail="Invalid token")
        if users[0].get("email") != user_data.email:
            raise HTTPException(status_code=400, detail="Token email mismatch")
        uid = users[0].get("localId")

    elif signup_req.password:
        async with httpx.AsyncClient() as client:
            fb_res = await client.post(
                f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={settings.FIREBASE_API_KEY}",
                json={"email": user_data.email, "password": signup_req.password, "returnSecureToken": True},
            )
        if fb_res.status_code == 200:
            uid = fb_res.json().get("localId")
        elif fb_res.status_code == 400 and fb_res.json().get("error", {}).get("message") == "EMAIL_EXISTS":
            async with httpx.AsyncClient() as client:
                login_res = await client.post(
                    f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={settings.FIREBASE_API_KEY}",
                    json={"email": user_data.email, "password": signup_req.password, "returnSecureToken": True},
                )
            if login_res.status_code == 200:
                uid = login_res.json().get("localId")
            else:
                raise HTTPException(status_code=400, detail="Account exists but password is wrong")
        else:
            raise HTTPException(status_code=fb_res.status_code, detail=fb_res.json().get("error", {}).get("message"))
    else:
        raise HTTPException(status_code=400, detail="Either password or id_token required")

    user_data.firebase_uid = uid
    return await user_service.create_user(user_data)


# ── Citizen Firebase Login ──────────────────────────────────────────────────

@router.post("/firebase-login", response_model=UserInDB)
async def firebase_login(body: FirebaseLogin, response: Response):
    """Verify a Firebase ID token and set a session cookie."""
    async with httpx.AsyncClient() as client:
        verify_res = await client.post(
            f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={settings.FIREBASE_API_KEY}",
            json={"idToken": body.idToken},
        )
    if verify_res.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid Firebase token")

    users = verify_res.json().get("users", [])
    if not users:
        raise HTTPException(status_code=401, detail="User not found in Firebase")

    uid = users[0].get("localId")
    email = users[0].get("email")

    user = await user_service.get_user_by_firebase_uid(uid) or await user_service.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Please complete signup.")

    _set_session_cookie(response, uid)
    return user


# ── Official Login (Officer / Ministry / CM) ────────────────────────────────

@router.post("/official-login", response_model=UserInDB)
async def official_login(body: OfficialLogin, response: Response):
    """Login for government officials — verifies bcrypt hash against Neon DB."""
    async with get_db_ctx() as session:
        result = await session.execute(select(UserDB).where(UserDB.email == body.email))
        user_model = result.scalar_one_or_none()

    if not user_model:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user_model.role == "citizen":
        raise HTTPException(status_code=401, detail="Use citizen login for this account")

    if user_model.password_hash:
        if not bcrypt.checkpw(body.password.encode(), user_model.password_hash.encode()):
            raise HTTPException(status_code=401, detail="Invalid credentials")

    _set_session_cookie(response, user_model.firebase_uid or user_model.id)
    return UserInDB(**user_model.to_dict())


# ── Profile ─────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserInDB)
async def get_my_profile(current_user: UserInDB = Depends(get_current_user)):
    return current_user


# ── Logout ──────────────────────────────────────────────────────────────────

@router.post("/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("access_token")
    if token:
        await user_service.blacklist_token(token)
    response.delete_cookie("access_token", path="/")
    return {"message": "Logged out successfully"}


# ── Helpers ─────────────────────────────────────────────────────────────────

def _set_session_cookie(response: Response, value: str) -> None:
    response.set_cookie(
        key="access_token",
        value=value,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=3600,
        path="/",
    )
