from fastapi import APIRouter

from app.schemas.response import SuccessResponse
from app.schemas.system import HealthData


router = APIRouter()


@router.get(
    "/health",
    response_model=SuccessResponse[HealthData],
    summary="서버 상태 확인",
    description="백엔드 애플리케이션의 실행 상태를 확인합니다.",
)
async def health_check() -> SuccessResponse[HealthData]:
    return SuccessResponse(
        message="서버가 정상적으로 실행 중입니다.",
        data=HealthData(),
    )
