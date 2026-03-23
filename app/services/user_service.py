from app.db.mongodb import db_client
from app.schemas.user import UserCreate, UserInDB
from fastapi.encoders import jsonable_encoder
import hashlib

async def create_user(user_in: UserCreate) -> UserInDB:
    user_dict = jsonable_encoder(user_in)
    
    # Optional fields or extra logic can go here if needed
    
    result = await db_client.db["users"].insert_one(user_dict)
    created_user = await db_client.db["users"].find_one({"_id": result.inserted_id})
    if created_user and "_id" in created_user:
        created_user["_id"] = str(created_user["_id"])
    return UserInDB(**created_user)

async def get_user_by_auth0_id(auth0_id: str) -> UserInDB | None:
    user = await db_client.db["users"].find_one({"auth0_id": auth0_id})
    if user:
        if "_id" in user:
            user["_id"] = str(user["_id"])
        return UserInDB(**user)
    return None

async def get_user_by_email(email: str) -> UserInDB | None:
    user = await db_client.db["users"].find_one({"email": email})
    if user:
        if "_id" in user:
            user["_id"] = str(user["_id"])
        return UserInDB(**user)
    return None

async def blacklist_token(token: str):
    hashed_token = hashlib.sha256(token.encode()).hexdigest()
    await db_client.db["blacklisted_tokens"].insert_one({"hashed_token": hashed_token})

async def is_token_blacklisted(token: str) -> bool:
    hashed_token = hashlib.sha256(token.encode()).hexdigest()
    record = await db_client.db["blacklisted_tokens"].find_one({"hashed_token": hashed_token})
    return record is not None
