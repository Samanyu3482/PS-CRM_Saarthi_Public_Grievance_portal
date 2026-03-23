import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

MONGODB_URI = "mongodb://localhost:27017/saarthi_db"

async def seed():
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client.saarthi_db
    users_collection = db["users"]

    test_users = [
        {
            "auth0_id": "test_officer_id",
            "name": "Test Officer",
            "email": "officer@test.com",
            "phone": "9876543210",
            "role": "officer",
            "department": "Public Works",
            "city": "Mumbai",
            "employee_id": "OFF-001"
        },
        {
            "auth0_id": "test_ministry_id",
            "name": "Test Ministry",
            "email": "ministry@test.com",
            "phone": "9876543211",
            "role": "ministry",
            "ministry_name": "Ministry of Urban Development",
            "designation": "Joint Secretary",
            "employee_id": "MIN-001"
        }
    ]

    for user in test_users:
        await users_collection.update_one(
            {"email": user["email"]},
            {"$set": user},
            upsert=True
        )
    print("Test accounts seeded successfully: officer@test.com, ministry@test.com")

if __name__ == "__main__":
    asyncio.run(seed())
