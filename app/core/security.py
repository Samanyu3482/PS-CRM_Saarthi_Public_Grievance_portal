import jwt
import httpx
from fastapi import HTTPException, Security, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

security = HTTPBearer(auto_error=False)

# ── Internal JWT for WhatsApp / service-to-service calls ────
_INTERNAL_SECRET = "pscrm-internal-whatsapp-service-key"
_INTERNAL_ALGORITHM = "HS256"


def create_internal_token(sub: str) -> str:
    """
    Create a lightweight internal JWT for WhatsApp users.
    These tokens are only used server-side by the agent's tool HTTP calls.
    """
    return jwt.encode(
        {"sub": sub, "_internal": True},
        _INTERNAL_SECRET,
        algorithm=_INTERNAL_ALGORITHM,
    )


def _decode_internal_token(token: str) -> dict | None:
    """Try to decode as an internal JWT. Returns payload or None."""
    try:
        payload = jwt.decode(token, _INTERNAL_SECRET, algorithms=[_INTERNAL_ALGORITHM])
        if payload.get("_internal"):
            return {"sub": payload["sub"], "_raw_token": token}
    except (jwt.InvalidTokenError, Exception):
        pass
    return None


async def decode_firebase_token(token: str) -> dict:
    # ── Try internal token first (WhatsApp users) ─────────
    internal = _decode_internal_token(token)
    if internal:
        return internal

    # ── Firebase verification ─────────────────────────────
    try:
        verification_url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={settings.FIREBASE_API_KEY}"
        async with httpx.AsyncClient() as client:
            verify_response = await client.post(
                verification_url,
                json={"idToken": token}
            )
        
        if verify_response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Firebase token")
            
        token_data = verify_response.json()
        if "users" not in token_data or len(token_data["users"]) == 0:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found in Firebase")
            
        user_info = token_data["users"][0]
        # Return a payload that mimics the old JWT 'sub' field
        payload = {"sub": user_info.get("localId"), "email": user_info.get("email"), "_raw_token": token}
        return payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Token Validation Error: {str(e)}")

async def verify_token(credentials: HTTPAuthorizationCredentials | None = Security(security)):
    if credentials is None:
        return None
    token = credentials.credentials
    return await decode_firebase_token(token)

def verify_token_from_cookie(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing access token cookie")
    # In standard cookie flow, the token is simply the UID currently
    return {"sub": token, "_raw_token": token}
