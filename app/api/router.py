from fastapi import APIRouter

from app.api.endpoints.home import router as home_router
from app.api.endpoints.health import router as health_router
from app.api.endpoints.tasks import router as task_router


api_router = APIRouter()
api_router.include_router(home_router, tags=["home"])
api_router.include_router(health_router, tags=["health"])
api_router.include_router(task_router, tags=["tasks"])
