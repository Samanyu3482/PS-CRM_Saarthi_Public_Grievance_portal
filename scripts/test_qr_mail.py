"""Quick test script to debug the QR-email flow."""
import asyncio, sys, os
sys.path.insert(0, os.getcwd())

async def main():
    from app.db.mongodb import connect_to_mongo, db_client
    await connect_to_mongo()

    # Get a real complaint
    real = await db_client.db["complaints"].find_one({"is_spam": {"$ne": True}})
    cid = str(real["_id"]) if real else "TEST-001"
    print(f"Using complaint ID: {cid}")

    from app.services.mail_service import send_complaint_emails
    send_complaint_emails(
        complaint_id=cid,
        title=real.get("title", "Test") if real else "Test",
        description=real.get("description", "Test desc") if real else "Test desc",
        ministry=real.get("ministry", "Ministry of Power") if real else "Ministry of Power",
        department=real.get("department", "Testing") if real else "Testing",
        location={"address": "Sector 15", "city": "Chandigarh", "state": "Punjab", "pincode": "160015"},
        priority="medium",
        citizen_name="Test User",
        citizen_email="saarthii.pscrm@gmail.com",
    )
    print("✅ Done! Check email inbox.")

asyncio.run(main())
