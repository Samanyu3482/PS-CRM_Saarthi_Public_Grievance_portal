"""Debug: test only the citizen email with QR to see the exact error."""
import asyncio, sys, os, traceback
sys.path.insert(0, os.getcwd())

async def main():
    from app.db.mongodb import connect_to_mongo, db_client
    await connect_to_mongo()

    real = await db_client.db["complaints"].find_one({"is_spam": {"$ne": True}})
    cid = str(real["_id"])
    print(f"Complaint ID: {cid}")

    # Step 1: Test QR generation
    print("\n--- Step 1: Generating QR code ---")
    try:
        from app.services.mail_service import _generate_qr_png_bytes
        qr_bytes = _generate_qr_png_bytes(f"http://localhost:5173/track/{cid}")
        print(f"✅ QR generated: {len(qr_bytes)} bytes")
    except Exception:
        print("❌ QR generation FAILED:")
        traceback.print_exc()
        return

    # Step 2: Test building citizen HTML
    print("\n--- Step 2: Building citizen HTML ---")
    try:
        from app.services.mail_service import _build_citizen_html
        html = _build_citizen_html(
            complaint_id=cid,
            title="Test",
            description="Test desc",
            ministry="Ministry of Water",
            department="Testing",
            location={"address": "A", "city": "B", "state": "C", "pincode": "123456"},
            priority="medium",
            citizen_name="Test",
            filed_at="03 Apr 2026",
            tracking_url=f"http://localhost:5173/track/{cid}",
        )
        print(f"✅ HTML built: {len(html)} chars")
    except Exception:
        print("❌ HTML build FAILED:")
        traceback.print_exc()
        return

    # Step 3: Test sending citizen email with QR
    print("\n--- Step 3: Sending citizen email with QR ---")
    try:
        from app.services.mail_service import _send_email
        _send_email(
            to_email="saarthii.pscrm@gmail.com",
            subject="[TEST] Citizen email with QR",
            html_body=html,
            inline_images={"qr_tracking": qr_bytes},
        )
        print("✅ Citizen email sent!")
    except Exception:
        print("❌ Email sending FAILED:")
        traceback.print_exc()

asyncio.run(main())
