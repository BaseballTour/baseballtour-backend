from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.schemas.response import SuccessResponse
from app.schemas.system import RootData
from app.api.openapi_normal_examples import install_normal_openapi_examples


app = FastAPI(
    title=settings.app_name,
    description="KBO 원정 직관 여행 서비스 백엔드 API",
    version=settings.app_version,
    debug=settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Idempotency-Key",
    ],
)

register_exception_handlers(app)

app.include_router(
    api_router,
    prefix=settings.api_v1_prefix,
)


@app.get(
    "/",
    response_model=SuccessResponse[RootData],
    tags=["Root"],
    summary="API 기본 정보",
)
async def root() -> SuccessResponse[RootData]:
    return SuccessResponse(
        data=RootData(
            name=settings.app_name,
            environment=settings.app_env,
        ),
    )


install_normal_openapi_examples(app)
