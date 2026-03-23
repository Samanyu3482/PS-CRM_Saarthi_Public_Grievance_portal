from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

class MongoDB:
    client: AsyncIOMotorClient = None
    db = None

db_client = MongoDB()

async def connect_to_mongo():
    try:
        # Added serverSelectionTimeoutMS to quickly fail if credentials/IP whitelist are wrong
        db_client.client = AsyncIOMotorClient(settings.MONGODB_URI, serverSelectionTimeoutMS=5000)
        # Provide 'pscrm' as a fallback in case the Atlas URI doesn't specify a default database
        db_client.db = db_client.client.get_default_database("pscrm")
        
        # Force a connection check to verify everything is working immediately on startup
        await db_client.client.admin.command('ping')
        
        if "mongodb+srv://" in settings.MONGODB_URI:
            print("🚀 Successfully connected to MongoDB Atlas (Cloud)!")
        elif "localhost" in settings.MONGODB_URI or "127.0.0.1" in settings.MONGODB_URI:
            print("🏠 Successfully connected to Local MongoDB!")
        else:
            print("✅ Successfully connected to MongoDB!")
            
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB! Please check your connection string, username/password, and IP Whitelist. Error: {e}")

async def close_mongo_connection():
    if db_client.client:
        db_client.client.close()
