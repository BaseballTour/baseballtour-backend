import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException
from app.schemas.base import to_camel
from app.schemas.response import ErrorBody, ErrorDetail, ErrorResponse


logger = logging.getLogger(__name__)


HTTP_ERROR_INFO: dict[int, tuple[str, str]] = {
    400: ("BAD_REQUEST", "잘못된 요청입니다."),
    401: ("AUTH_TOKEN_INVALID", "인증 정보가 올바르지 않습니다."),
    403: ("AUTH_FORBIDDEN", "요청한 작업을 수행할 권한이 없습니다."),
    404: ("NOT_FOUND", "요청한 리소스를 찾을 수 없습니다."),
    405: ("METHOD_NOT_ALLOWED", "허용되지 않은 요청 방식입니다."),
    409: ("CONFLICT", "현재 상태와 충돌하는 요청입니다."),
    429: ("RATE_LIMITED", "요청 횟수 제한을 초과했습니다."),
    502: ("EXTERNAL_API_INVALID_RESPONSE", "외부 API 응답 처리에 실패했습니다."),
    503: ("EXTERNAL_API_UNAVAILABLE", "외부 서비스를 일시적으로 사용할 수 없습니다."),
}


def format_validation_field(location: tuple[Any, ...]) -> str:
    ignored_locations = {
        "body",
        "query",
        "path",
        "header",
        "cookie",
    }

    parts: list[str] = []

    for value in location:
        if isinstance(value, str):
            if value in ignored_locations:
                continue

            parts.append(to_camel(value))
        else:
            parts.append(str(value))

    return ".".join(parts)


def create_error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: list[Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    response = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            details=details or [],
        ),
    )

    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(
            response.model_dump(by_alias=True),
        ),
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request,
        exc: AppException,
    ) -> JSONResponse:
        details = exc.details

        if details is None:
            normalized_details: list[Any] = []
        elif isinstance(details, list):
            normalized_details = details
        else:
            normalized_details = [details]

        return create_error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            details=normalized_details,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        details = [
            ErrorDetail(
                field=format_validation_field(error["loc"]),
                reason=error["msg"],
            ).model_dump(by_alias=True)
            for error in exc.errors()
        ]

        return create_error_response(
            status_code=422,
            code="VALIDATION_ERROR",
            message="입력값을 확인해 주세요.",
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

        details: list[Any] = []

        if not isinstance(exc.detail, str):
            details = [exc.detail]

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
