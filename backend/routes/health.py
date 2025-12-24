from fastapi import APIRouter

router = APIRouter(
    prefix="/api",
    tags=["health"]
)

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "96sooq-backend"
    }
