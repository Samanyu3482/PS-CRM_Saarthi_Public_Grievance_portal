import asyncio
from app.db.mongodb import db_client

async def ensure_admin():
    admin_email = "admin@saarthi.gov.in"
    admin = await db_client.db["users"].find_one({"email": admin_email})
    if not admin:
        print(f"Admin user with email {admin_email} not found.")
        return
    updates = {}
    if admin.get("role") != "admin":
        updates["role"] = "admin"
    if not admin.get("auth0_id"):
        updates["auth0_id"] = str(admin["_id"])  # use MongoDB _id as auth0_id
    if updates:
        await db_client.db["users"].update_one({"_id": admin["_id"]}, {"$set": updates})
        print(f"Updated admin user: {updates}")
    else:
        print("Admin user already has correct role and auth0_id.")

if __name__ == "__main__":
    asyncio.run(ensure_admin())
