from fastapi import FastAPI, Query
from fastapi.testclient import TestClient

from app.core.exception_handlers import register_exception_handlers
from app.core.exceptions import AppException
from app.main import app


client = TestClient(
    app,
    raise_server_exceptions=False,
)


def create_error_test_app() -> FastAPI:
    test_app = FastAPI(debug=False)
    register_exception_handlers(test_app)

    @test_app.get("/validation")
    async def validation_endpoint(
        count: int = Query(ge=1),
    ) -> dict[str, int]:
        return {
            "count": count,
        }

    @test_app.get("/custom-error")
    async def custom_error_endpoint() -> None:
        raise AppException(
            status_code=404,
            code="TRIP_NOT_FOUND",
            message="여행 정보를 찾을 수 없습니다.",
        )

    @test_app.get("/unexpected-error")
    async def unexpected_error_endpoint() -> None:
        raise RuntimeError("테스트용 서버 오류")

    return test_app


error_client = TestClient(
    create_error_test_app(),
    raise_server_exceptions=False,
)


def test_health_success_response() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "status": "healthy",
        },
    }


def test_not_found_response() -> None:
    response = client.get("/api/v1/not-found")

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "error": {
            "code": "NOT_FOUND",
            "message": "요청한 리소스를 찾을 수 없습니다.",
            "details": [],
        },
    }


def test_validation_error_response() -> None:
    response = error_client.get(
        "/validation",
        params={
            "count": 0,
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "success": False,
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "입력값을 확인해 주세요.",
            "details": [
                {
                    "field": "count",
                    "reason": "Input should be greater than or equal to 1",
                }
            ],
        },
    }


def test_custom_exception_response() -> None:
    response = error_client.get("/custom-error")

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "error": {
            "code": "TRIP_NOT_FOUND",
            "message": "여행 정보를 찾을 수 없습니다.",
            "details": [],
        },
    }


def test_unexpected_exception_response() -> None:
    response = error_client.get("/unexpected-error")

    assert response.status_code == 500
    assert response.json() == {
        "success": False,
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "서버 내부 오류가 발생했습니다.",
            "details": [],
        },
    }
