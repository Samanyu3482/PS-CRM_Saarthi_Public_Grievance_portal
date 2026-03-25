import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

async def main():
    load_dotenv()
    mongo_uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("MONGODB_DB_NAME", "pscrm")
    
    client = AsyncIOMotorClient(mongo_uri)
    db = client[db_name]
    
    print(f"Checking collection: complaints")
    count = await db["complaints"].count_documents({})
    print(f"Total complaints: {count}")
    
    if count > 0:
        cursor = db["complaints"].find().limit(5)
        async for doc in cursor:
            print(f"- {doc.get('title')} | status={doc.get('status')}")
    else:
        print("No complaints found.")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(main())
