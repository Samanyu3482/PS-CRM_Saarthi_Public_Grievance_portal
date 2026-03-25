import httpx
from fastapi import HTTPException, Security, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

security = HTTPBearer(auto_error=False)

async def decode_firebase_token(token: str) -> dict:
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
