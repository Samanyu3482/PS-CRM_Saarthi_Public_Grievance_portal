from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.mongodb import connect_to_mongo, close_mongo_connection

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.routes import auth, complaints, routing, dashboard_routes, analytics_routes
app.include_router(auth.router)
app.include_router(complaints.router)
app.include_router(routing.router)
app.include_router(dashboard_routes.router)
app.include_router(analytics_routes.router)

@app.get("/")
async def root():
    return {"message": "Welcome to PS-CRM API"}
