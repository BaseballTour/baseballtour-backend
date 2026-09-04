from fastapi import APIRouter
from app.api.openapi_responses import BASE_API_ERROR_RESPONSES

from app.api.v1.endpoints.attendance_logs import router as attendance_logs_router
from app.api.v1.endpoints.favorite_collections import router as favorite_collections_router
from app.api.v1.endpoints.accommodations import router as accommodations_router
from app.api.v1.endpoints.games import router as games_router
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.media import router as media_router
from app.api.v1.endpoints.teams import router as teams_router
from app.api.v1.endpoints.terms import router as terms_router
from app.api.v1.endpoints.trips import router as trips_router
from app.api.v1.endpoints.tour import router as tour_router
from app.api.v1.endpoints.users import router as users_router


api_router = APIRouter(responses=BASE_API_ERROR_RESPONSES)

api_router.include_router(
    attendance_logs_router,
    tags=["Attendance Logs"],
)

api_router.include_router(
    accommodations_router,
    tags=["Accommodations"],
)

api_router.include_router(
    health_router,
    tags=["Health"],
)


api_router.include_router(
    favorite_collections_router,
    tags=["Favorite Collections"],
)

api_router.include_router(
    games_router,
    tags=["Games"],
)

api_router.include_router(
    media_router,
    tags=["Media"],
)

api_router.include_router(
    teams_router,
    tags=["Teams"],
)

api_router.include_router(
    terms_router,
    tags=["Terms"],
)

api_router.include_router(
    trips_router,
    tags=["Trips"],
)

api_router.include_router(
    users_router,
    tags=["Users"],
)

api_router.include_router(tour_router)
