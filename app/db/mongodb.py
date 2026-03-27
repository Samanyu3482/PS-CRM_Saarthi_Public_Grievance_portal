from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConfigurationError, OperationFailure, ServerSelectionTimeoutError
import certifi
from app.core.config import settings

class MongoDB:
    client: AsyncIOMotorClient = None
    db = None

db_client = MongoDB()

async def connect_to_mongo():
    try:
        uri = settings.MONGODB_URI.strip()

        if "<db_password>" in uri:
            print("❌ MongoDB URI still contains <db_password>. Replace it with the real Atlas DB user password.")
            return

        is_atlas = "mongodb+srv://" in uri or "mongodb.net" in uri

        client_kwargs = {
            "serverSelectionTimeoutMS": 30000,
            "connectTimeoutMS": 20000,
            "socketTimeoutMS": 20000,
            "maxPoolSize": 50,
        }

        # TLS must only be forced for Atlas/cloud hosts.
        if is_atlas:
            client_kwargs.update({
                "tls": True,
                "tlsCAFile": certifi.where(),
            })

        db_client.client = AsyncIOMotorClient(uri, **client_kwargs)

        # Provide 'pscrm' as a fallback in case the Atlas URI doesn't specify a default database.
        db_client.db = db_client.client.get_default_database("pscrm")
        
        # Force a connection check to verify everything is working immediately on startup.
        await db_client.client.admin.command('ping')
        
        if "mongodb+srv://" in settings.MONGODB_URI or "mongodb.net" in settings.MONGODB_URI:
            print("🚀 Successfully connected to MongoDB Atlas (Cloud)!")
        elif "localhost" in settings.MONGODB_URI or "127.0.0.1" in settings.MONGODB_URI:
            print("🏠 Successfully connected to Local MongoDB!")
        else:
            print("✅ Successfully connected to MongoDB!")

    except ServerSelectionTimeoutError as e:
        message = str(e)
        if "SSL handshake failed" in message:
            print(
                "❌ MongoDB TLS handshake failed. Most likely causes: "
                "1) Atlas IP Access List does not include your current IP, "
                "2) corporate firewall/proxy intercepting TLS, "
                "3) wrong Atlas host in URI. "
                f"Details: {message}"
            )
        else:
            print(f"❌ MongoDB server selection timeout: {message}")
    except OperationFailure as e:
        print(f"❌ MongoDB authentication/authorization failed: {e}")
    except ConfigurationError as e:
        print(f"❌ MongoDB configuration error (URI/options): {e}")
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")

async def close_mongo_connection():
    if db_client.client:
        db_client.client.close()
