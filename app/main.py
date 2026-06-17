from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import engine, Base
from app.db.models import UserDB, ComplaintDB, DepartmentDB, OfficerDB, NotificationDB, WhatsAppSessionDB, BlacklistedTokenDB
from fastapi.staticfiles import StaticFiles
import pathlib
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("PostgreSQL tables initialized successfully!")

    # ── Auto-start ngrok tunnel for WhatsApp webhook ──────
    ngrok_tunnel = None
    try:
        from app.core.config import settings as _s
        if _s.NGROK_AUTH_TOKEN:
            from pyngrok import ngrok, conf
            conf.get_default().auth_token = _s.NGROK_AUTH_TOKEN
            ngrok_tunnel = ngrok.connect(8000, "http")
            public_url = ngrok_tunnel.public_url
            print(f"\n{'='*60}")
            print(f"  NGROK TUNNEL ACTIVE")
            print(f"  Public URL : {public_url}")
            print(f"  Webhook    : {public_url}/whatsapp/webhook")
            print(f"  -> Paste this webhook URL in Meta Developer Dashboard")
            print(f"{'='*60}\n")
    except Exception as e:
        print(f"Ngrok tunnel failed (non-fatal): {e}")

    yield

    # Cleanup
    if ngrok_tunnel:
        from pyngrok import ngrok
        ngrok.disconnect(ngrok_tunnel.public_url)
    await engine.dispose()
    print("PostgreSQL connection pool disposed.")

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
from app.api.routes.whatsapp import router as whatsapp_router
app.include_router(whatsapp_router)

# serve uploaded files
basedir = pathlib.Path(__file__).resolve().parents[1]
uploads_dir = basedir / "uploads"
uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

@app.get("/")
async def root():
    return {"message": "Welcome to PS-CRM API"}
