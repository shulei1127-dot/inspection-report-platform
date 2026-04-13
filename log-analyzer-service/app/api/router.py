from fastapi import APIRouter

from app.api.endpoints import analyze, health


router = APIRouter()
router.include_router(health.router)
router.include_router(analyze.router)
