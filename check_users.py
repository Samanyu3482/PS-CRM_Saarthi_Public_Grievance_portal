import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

async def check_users():
    load_dotenv()
    mongo_uri = os.getenv("MONGODB_URI")
    client = AsyncIOMotorClient(mongo_uri)
    db = client.get_default_database("pscrm")
    
    # Check for moksh8008@gmail.com
    email = "moksh8008@gmail.com"
    user = await db["users"].find_one({"email": email})
    if user:
        print(f"User {email} found: ID={user['_id']}, auth0_id={user.get('auth0_id')}")
    else:
        print(f"User {email} NOT FOUND in MongoDB")
    
    # List all emails
    all_users = await db["users"].find({}, {"email": 1}).to_list(100)
    print("All users in DB:")
    for u in all_users:
        print(f"- {u.get('email')}")

if __name__ == "__main__":
    asyncio.run(check_users())
