import hashlib
from app.schemas.user import UserCreate, UserInDB
from app.db.database import get_db_ctx
from app.db.models import UserDB, BlacklistedTokenDB
from sqlalchemy import select

async def create_user(user_in: UserCreate) -> UserInDB:
    # UserCreate is polymorphic; we call model_dump() to convert it
    user_dict = user_in.model_dump()
    
    db_user = UserDB(
        firebase_uid=user_dict.get("firebase_uid"),
        auth0_id=user_dict.get("auth0_id"),
        name=user_dict.get("name"),
        email=user_dict.get("email"),
        phone=user_dict.get("phone"),
        role=user_dict.get("role").value if hasattr(user_dict.get("role"), "value") else user_dict.get("role"),
        
        # citizen fields
        address=user_dict.get("address"),
        city=user_dict.get("city"),
        state=user_dict.get("state"),
        pincode=user_dict.get("pincode"),
        
        # officer / mc / ministry / delhi_cm fields
        department=user_dict.get("department"),
        employee_id=user_dict.get("employee_id"),
        ministry_name=user_dict.get("ministry_name"),
        designation=user_dict.get("designation"),
        
        # mp_mla fields
        constituency=user_dict.get("constituency"),
        party_name=user_dict.get("party_name"),
        
        # password hash (for official login)
        password_hash=user_dict.get("password_hash"),
    )
    
    async with get_db_ctx() as session:
        session.add(db_user)
        await session.commit()
        await session.refresh(db_user)
        user_data = db_user.to_dict()
        
    return UserInDB(**user_data)

async def get_user_by_firebase_uid(firebase_uid: str) -> UserInDB | None:
    async with get_db_ctx() as session:
        stmt = select(UserDB).where(UserDB.firebase_uid == firebase_uid)
        result = await session.execute(stmt)
        user_model = result.scalar_one_or_none()
        if user_model:
            return UserInDB(**user_model.to_dict())
    return None

async def get_user_by_email(email: str) -> UserInDB | None:
    async with get_db_ctx() as session:
        stmt = select(UserDB).where(UserDB.email == email)
        result = await session.execute(stmt)
        user_model = result.scalar_one_or_none()
        if user_model:
            return UserInDB(**user_model.to_dict())
    return None

async def blacklist_token(token: str):
    hashed_token = hashlib.sha256(token.encode()).hexdigest()
    async with get_db_ctx() as session:
        db_token = BlacklistedTokenDB(hashed_token=hashed_token)
        session.add(db_token)
        await session.commit()

async def is_token_blacklisted(token: str) -> bool:
    hashed_token = hashlib.sha256(token.encode()).hexdigest()
    async with get_db_ctx() as session:
        stmt = select(BlacklistedTokenDB).where(BlacklistedTokenDB.hashed_token == hashed_token)
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None
