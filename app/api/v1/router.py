from fastapi import APIRouter

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.teams import router as teams_router
from app.api.v1.endpoints.tour import router as tour_router
from app.api.v1.endpoints.users import router as users_router


api_router = APIRouter()

api_router.include_router(
    health_router,
    tags=["Health"],
)

api_router.include_router(
    teams_router,
    tags=["Teams"],
)

api_router.include_router(
    users_router,
    tags=["Users"],
)

api_router.include_router(tour_router)
