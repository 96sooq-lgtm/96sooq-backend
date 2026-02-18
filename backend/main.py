from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from config.settings import Settings
from routes import health
from routes.admin import router as admin_router
from routes.auth import router as auth_router
from routes.categories import admin_router as category_admin_router
from routes.categories import user_router as category_user_router
from routes.stores import router as stores_router
from routes.stores import admin_router as admin_stores_router
from routes.listings import router as listings_router
from routes.listings import admin_router as admin_listings_router
from routes.storage import router as storage_router
from routes.subscriptions import admin_router as admin_subscriptions_router
from routes.subscriptions import user_router as user_subscriptions_router
from routes.banners import router as banners_router
from routes.banners import admin_router as admin_banners_router
from routes.locations import router as locations_router
from routes.payments import router as payments_router

# Load settings
settings = Settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting 96sooq Backend API...")
    yield
    # Shutdown
    print("Shutting down 96sooq Backend API...")

# Create FastAPI app
app = FastAPI(
    title="96sooq API",
    description="Backend API for 96sooq mobile and web apps",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(category_admin_router)
app.include_router(category_user_router)
app.include_router(locations_router)
app.include_router(stores_router)
app.include_router(admin_stores_router)
app.include_router(listings_router)
app.include_router(admin_listings_router)
app.include_router(storage_router)
app.include_router(admin_subscriptions_router)
app.include_router(user_subscriptions_router)
app.include_router(banners_router)
app.include_router(admin_banners_router)
app.include_router(payments_router)


@app.get("/")
async def root():
    return {"message": "96sooq Backend API", "version": "1.0.0"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.api_port,
        reload=settings.debug
    )
