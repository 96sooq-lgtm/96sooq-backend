from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import traceback
from config.settings import Settings
from utils.logger import setup_logging, get_logger
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
    RATE_LIMITING_ENABLED = True
except ImportError:
    limiter = None
    RATE_LIMITING_ENABLED = False
from routes import health
from routes.admin import router as admin_router
from routes.auth import router as auth_router
from routes.users import admin_router as admin_users_router
from routes.users import user_router as users_router
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
from routes.payments import admin_router as admin_payments_router
from routes.favorites import router as favorites_router
from routes.chats import router as chats_router
from routes.chats import admin_router as admin_chats_router
from routes.feed import router as feed_router

# Setup logging
setup_logging()
logger = get_logger("main")

# Load settings
settings = Settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting 96sooq Backend API...")
    yield
    logger.info("Shutting down 96sooq Backend API...")

# Create FastAPI app
app = FastAPI(
    title="96sooq API",
    description="Backend API for 96sooq mobile and web apps",
    version="1.0.0",
    lifespan=lifespan
)

# -----------------------------------------------
# GLOBAL EXCEPTION HANDLER
# Catches all unhandled exceptions → returns 500
# with clean JSON instead of raw stack trace
# -----------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}: "
        f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
    )
    
    # We expose the exact error and traceback in development/testing
    # so the frontend developers can immediately know what went wrong
    # without checking the server logs.
    error_detail = {
        "detail": str(exc) or "An internal error occurred.",
        "error_type": type(exc).__name__,
        "path": request.url.path,
        "method": request.method
    }
    
    if settings.debug:
        error_detail["traceback"] = traceback.format_exc().splitlines()
        
    return JSONResponse(
        status_code=500,
        content=error_detail
    )

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
if RATE_LIMITING_ENABLED:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    logger.info("Rate limiting enabled via slowapi")

# Include routers
app.include_router(health.router)
app.include_router(admin_router)
app.include_router(admin_users_router)
app.include_router(users_router)
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
app.include_router(admin_payments_router)
app.include_router(favorites_router)
app.include_router(chats_router)
app.include_router(admin_chats_router)
app.include_router(feed_router)


@app.get("/feed")
@app.get("/feed/")
async def feed_redirect(request: Request):
    from fastapi.responses import RedirectResponse
    query_params = str(request.query_params)
    url = f"/api/feed/?{query_params}" if query_params else "/api/feed/"
    return RedirectResponse(url=url)


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
