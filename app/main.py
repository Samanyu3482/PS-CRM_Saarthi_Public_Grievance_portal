from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.mongodb import connect_to_mongo, close_mongo_connection
from fastapi.staticfiles import StaticFiles
import pathlib

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()

app = FastAPI(
    title="Smart Public Service CRM",
    description="Backend for PS-CRM with role-based authentication.",
    version="1.0.0",
    lifespan=lifespan
)

from app.core.config import settings

allowed_origins = [o.strip() for o in settings.FRONTEND_ORIGINS.split(',') if o.strip()]
# Ensure common dev origins are allowed
for dev_origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
    if dev_origin not in allowed_origins:
        allowed_origins.append(dev_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.routes import auth, complaints, routing, dashboard_routes, analytics_routes, notifications, admin
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(complaints.router)
app.include_router(routing.router)
app.include_router(dashboard_routes.router)
app.include_router(analytics_routes.router)
from app.api.routes.uploads import router as uploads_router
app.include_router(uploads_router)
app.include_router(notifications.router)

# serve uploaded files
basedir = pathlib.Path(__file__).resolve().parents[1]
uploads_dir = basedir / "uploads"
uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

@app.get("/")
async def root():
    return {"message": "Welcome to PS-CRM API"}


@app.get("/test-mail")
async def test_mail():
    """Quick endpoint to test the mail service with QR code — hit http://127.0.0.1:8000/test-mail"""
    from app.services.mail_service import send_complaint_emails
    from app.db.mongodb import db_client

    # Grab a real complaint so the QR code links to a valid tracking page
    real = await db_client.db["complaints"].find_one({"is_spam": {"$ne": True}})
    cid = str(real["_id"]) if real else "TEST-001"
    title = real.get("title", "Broken Street Lights in Sector 15") if real else "Broken Street Lights in Sector 15"
    desc = real.get("description", "Test description") if real else "Test description"
    ministry = real.get("ministry", "Ministry of Power") if real else "Ministry of Power"
    dept = real.get("department", "Electricity Distribution") if real else "Electricity Distribution"

    try:
        send_complaint_emails(
            complaint_id=cid,
            title=title,
            description=desc,
            ministry=ministry,
            department=dept,
            location={"address": "Sector 15 Main Road", "city": "Chandigarh", "state": "Punjab", "pincode": "160015"},
            priority="medium",
            citizen_name="Test User",
            citizen_email="saarthii.pscrm@gmail.com",  # sends to yourself for testing
        )
        return {
            "status": "success",
            "complaint_id": cid,
            "tracking_url": f"http://localhost:5173/track/{cid}",
            "message": "Test emails sent with QR code! Check inbox of saarthii.pscrm@gmail.com",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
