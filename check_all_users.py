import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

async def check():
    load_dotenv()
    mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017/pscrm")
    client = AsyncIOMotorClient(mongo_uri)
    db = client.get_default_database("pscrm")

    print("All users in DB:")
    async for u in db.users.find({}, {"email": 1, "role": 1, "user_type": 1, "auth0_id": 1, "name": 1}):
        role = u.get("role", "MISSING")
        user_type = u.get("user_type", "-")
        auth0_id = u.get("auth0_id", "(none)")
        print(f"  [{role}] {u.get('name','?')} | {u.get('email')} | auth0_id={auth0_id} | user_type={user_type}")

if __name__ == "__main__":
    asyncio.run(check())
