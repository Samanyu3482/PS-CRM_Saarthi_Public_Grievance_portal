import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

async def check():
    load_dotenv()
    mongo_uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("MONGODB_DB_NAME", "saarthi")
    client = AsyncIOMotorClient(mongo_uri)
    db = client[db_name]
    user = await db["users"].find_one({"email": "admin@saarthi.gov.in"})
    if user:
        print(f"User Found: {user.get('email')} | role: {user.get('role')}")
    else:
        print("Admin user not found.")
    client.close()

if __name__ == "__main__":
    asyncio.run(check())
