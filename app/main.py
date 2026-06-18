from contextlib import asynccontextmanager
import pathlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.db.database import engine, Base
from app.api.routes import auth, complaints, routing, dashboard_routes, analytics_routes, notifications, admin
from app.api.routes.uploads import router as uploads_router
from app.api.routes.whatsapp import router as whatsapp_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure all PostgreSQL tables exist on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Optional: ngrok tunnel for WhatsApp webhook (non-fatal if unavailable)
    ngrok_tunnel = None
    if settings.NGROK_AUTH_TOKEN:
        try:
            from pyngrok import ngrok, conf
            conf.get_default().auth_token = settings.NGROK_AUTH_TOKEN
            ngrok_tunnel = ngrok.connect(8000, "http")
            print(f"Ngrok tunnel active: {ngrok_tunnel.public_url}/whatsapp/webhook")
        except Exception as e:
            print(f"Ngrok tunnel skipped: {e}")

    yield

    if ngrok_tunnel:
        try:
            from pyngrok import ngrok
            ngrok.disconnect(ngrok_tunnel.public_url)
        except Exception:
            pass
    await engine.dispose()


app = FastAPI(
    title="Saarthi — Smart Public Grievance CRM",
    description="Role-based grievance management system for Delhi Government.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
_origins = [o.strip() for o in settings.FRONTEND_ORIGINS.split(",") if o.strip()]
for _dev in ("http://localhost:5173", "http://127.0.0.1:5173"):
    if _dev not in _origins:
        _origins.append(_dev)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(complaints.router)
app.include_router(routing.router)
app.include_router(dashboard_routes.router)
app.include_router(analytics_routes.router)
app.include_router(uploads_router)
app.include_router(notifications.router)
app.include_router(whatsapp_router)

# Static file serving for uploads
_uploads_dir = pathlib.Path(__file__).resolve().parents[1] / "uploads"
_uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_uploads_dir)), name="uploads")


@app.get("/", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": "Saarthi PS-CRM API"}
