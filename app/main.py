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

from app.api.routes import auth, complaints, routing, dashboard_routes, analytics_routes, notifications
app.include_router(auth.router)
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
