from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import (
    get_current_user_id,
)
from app.main import app
from app.schemas.attendance_log import (
    AttendanceLogRecord,
    AttendanceLogStatus,
)


USER_ID = "firebase-user-123"
TRIP_ID = "trip_001"
GAME_ID = "game_001"
PLAN_ID = "plan_001"

NOW = datetime(
    2026,
    8,
    19,
    3,
    0,
    tzinfo=timezone.utc,
)


def make_log_record(
    *,
    log_title: str = "사직 원정 직관 기록",
) -> AttendanceLogRecord:
    return AttendanceLogRecord(
        attendance_log_id="log_001",
        user_id=USER_ID,
        trip_id=TRIP_ID,
        game_id=GAME_ID,
        plan_id=PLAN_ID,
        log_title=log_title,
        summary_text=None,
        log_status=AttendanceLogStatus.DRAFT,
        created_at=NOW,
        updated_at=NOW,
        deleted_at=None,
    )


@pytest.fixture
def authenticated_client() -> TestClient:
    app.dependency_overrides[
        get_current_user_id
    ] = lambda: USER_ID

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_create_attendance_log_returns_created_draft(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.create_draft.return_value = (
        make_log_record()
    )

    with patch(
        (
            "app.api.v1.endpoints.attendance_logs."
            "AttendanceLogService"
        ),
        return_value=service,
    ):
        response = authenticated_client.post(
            "/api/v1/attendance-logs",
            json={
                "tripId": TRIP_ID,
                "logTitle": "사직 원정 직관 기록",
            },
        )

    assert response.status_code == 201

    body = response.json()

    assert body["success"] is True

    assert body["data"] == {
        "attendanceLogId": "log_001",
        "tripId": TRIP_ID,
        "gameId": GAME_ID,
        "planId": PLAN_ID,
        "logTitle": "사직 원정 직관 기록",
        "summaryText": None,
        "logStatus": "DRAFT",
        "createdAt": "2026-08-19T03:00:00Z",
        "updatedAt": "2026-08-19T03:00:00Z",
    }

    assert "userId" not in body["data"]
    assert "deletedAt" not in body["data"]

    service.create_draft.assert_called_once_with(
        user_id=USER_ID,
        trip_id=TRIP_ID,
        log_title="사직 원정 직관 기록",
    )


def test_create_attendance_log_accepts_missing_title(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.create_draft.return_value = (
        make_log_record(
            log_title="부산 직관 여행",
        )
    )

    with patch(
        (
            "app.api.v1.endpoints.attendance_logs."
            "AttendanceLogService"
        ),
        return_value=service,
    ):
        response = authenticated_client.post(
            "/api/v1/attendance-logs",
            json={
                "tripId": TRIP_ID,
            },
        )

    assert response.status_code == 201
    assert (
        response.json()["data"]["logTitle"]
        == "부산 직관 여행"
    )

    service.create_draft.assert_called_once_with(
        user_id=USER_ID,
        trip_id=TRIP_ID,
        log_title=None,
    )


def test_create_attendance_log_requires_trip_id(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.post(
        "/api/v1/attendance-logs",
        json={
            "logTitle": "사직 원정",
        },
    )

    assert response.status_code == 422

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_attendance_log_api_requires_authentication() -> None:
    app.dependency_overrides.clear()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/attendance-logs",
            json={
                "tripId": TRIP_ID,
            },
        )

    assert response.status_code == 401

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "AUTH_TOKEN_MISSING"
