import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException
from app.schemas.response import ErrorResponse


logger = logging.getLogger(__name__)


HTTP_ERROR_INFO: dict[int, tuple[str, str]] = {
    400: ("BAD_REQUEST", "잘못된 요청입니다."),
    401: ("UNAUTHORIZED", "인증이 필요합니다."),
    403: ("FORBIDDEN", "요청한 작업을 수행할 권한이 없습니다."),
    404: ("NOT_FOUND", "요청한 리소스를 찾을 수 없습니다."),
    405: ("METHOD_NOT_ALLOWED", "허용되지 않은 요청 방식입니다."),
    409: ("CONFLICT", "현재 상태와 충돌하는 요청입니다."),
}


def create_error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    response = ErrorResponse(
        code=code,
        message=message,
        details=details,
    )

    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(
            response.model_dump(exclude_none=True),
        ),
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request,
        exc: AppException,
    ) -> JSONResponse:
        return create_error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            details=exc.details,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        details = [
            {
                "field": ".".join(
                    str(location)
                    for location in error["loc"]
                ),
                "message": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors()
        ]

        return create_error_response(
            status_code=422,
            code="VALIDATION_ERROR",
            message="요청값이 올바르지 않습니다.",
            details=details,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        default_code, default_message = HTTP_ERROR_INFO.get(
            exc.status_code,
            ("HTTP_ERROR", "HTTP 요청 처리 중 오류가 발생했습니다."),
        )

        details = (
            exc.detail
            if not isinstance(exc.detail, str)
            else None
        )

        return create_error_response(
            status_code=exc.status_code,
            code=default_code,
            message=default_message,
            details=details,
            headers=exc.headers,
        )

    @app.exception_handler(Exception)
    async def unexpected_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.error(
            "처리되지 않은 서버 오류: %s %s",
            request.method,
            request.url.path,
            exc_info=(type(exc), exc, exc.__traceback__),
        )

        return create_error_response(
            status_code=500,
            code="INTERNAL_SERVER_ERROR",
            message="서버 내부 오류가 발생했습니다.",
        )
