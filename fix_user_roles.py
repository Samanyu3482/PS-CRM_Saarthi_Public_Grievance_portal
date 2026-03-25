import motor.motor_asyncio
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def fix_user_roles():
    uri = os.getenv("MONGODB_URI")
    if not uri:
        print("MONGODB_URI not found in environment")
        return

    client = motor.motor_asyncio.AsyncIOMotorClient(uri)
    db = client.pscrm
    
    # Standard roles we want to use
    role_map = {
        "citizen": "citizen",
        "officer": "officer",
        "ministry": "ministry",
        "mp/mla": "mp_mla",
        "mp_mla": "mp_mla",
        "municipal corporation": "mc",
        "mc": "mc",
        "admin": "admin"
    }
    
    print("Starting user data migration...")
    
    cursor = db.users.find({})
    users = await cursor.to_list(length=1000)
    
    migrated_role_count = 0
    auth0_count = 0
    
    for user in users:
        updates = {}
        user_id = user["_id"]
        
        # 1. Handle Role Migration
        current_role = user.get("role")
        current_type = user.get("user_type")
        
        if not current_role:
            # If role is missing, try to infer from user_type
            if current_type:
                new_role = role_map.get(current_type.lower(), "citizen")
            else:
                new_role = "citizen"
            updates["role"] = new_role
            migrated_role_count += 1
        
        # 2. Handle auth0_id population (Critical for admin/auth me sessions)
        if not user.get("auth0_id"):
            updates["auth0_id"] = str(user_id)
            auth0_count += 1
            
        if updates:
            await db.users.update_one({"_id": user_id}, {"$set": updates})
            
    print(f"✅ Migration complete!")
    print(f"   - Migrated role for {migrated_role_count} users.")
    print(f"   - Set auth0_id for {auth0_count} users.")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(fix_user_roles())
