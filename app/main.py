from fastapi import FastAPI

from app.core.config import get_settings
from app.routers.tour import router as tour_router


app = FastAPI(
    title="Baseball Tour Backend",
    version="0.1.0",
)

settings = get_settings()

app.include_router(tour_router)


@app.get("/")
def root():
    return {
        "message": "Baseball Tour Backend is running",
        "tourApiKeyLoaded": bool(settings.tour_api_key),
    }


@app.get("/health")
def health_check():
    return {
        "status": "ok",
    }