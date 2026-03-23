import jwt
from fastapi import HTTPException, Security, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

security = HTTPBearer()
jwks_url = f"{settings.AUTH0_ISSUER}.well-known/jwks.json"
jwks_client = jwt.PyJWKClient(jwks_url)


def decode_jwt(token: str) -> dict:
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=[settings.AUTH0_ALGORITHMS],
            audience=settings.AUTH0_API_AUDIENCE,
            issuer=settings.AUTH0_ISSUER,
        )
        payload["_raw_token"] = token
        return payload
    except jwt.exceptions.PyJWKClientError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error))
    except jwt.exceptions.DecodeError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error))
    except jwt.ExpiredSignatureError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"JWT Validation Error: {str(e)}")


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    return decode_jwt(token)


def verify_token_from_cookie(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing access token cookie")
    # Try to decode as JWT first, otherwise accept a dev-session token (auth0_id) for local development
    try:
        return decode_jwt(token)
    except HTTPException:
        # treat token as raw auth0_id for dev/local flow
        return {"sub": token, "_raw_token": token}
