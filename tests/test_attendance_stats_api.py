from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import (
    ActiveUserContext,
    get_current_active_user_context,
)
from app.main import app
from app.schemas.attendance_stats import (
    AttendanceStatsResponse,
)
from app.schemas.user import UserDocument


@pytest.fixture
def authenticated_client() -> TestClient:
    user = UserDocument(
        email="fan@example.com",
        nickname="테스트사용자",
        birth_year=2002,
        support_team_id="doosan",
        profile_image_url=None,
        onboarding_completed=True,
        created_at=datetime(
            2026,
            7,
            30,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        updated_at=datetime(
            2026,
            7,
            30,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        deleted_at=None,
    )

    app.dependency_overrides[
        get_current_active_user_context
    ] = lambda: ActiveUserContext(
        user_id="firebase-user-123",
        user=user,
    )

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_get_my_attendance_stats_api(
    authenticated_client: TestClient,
) -> None:
    service = Mock()

    service.get_stats.return_value = (
        AttendanceStatsResponse(
            away_trip_count=4,
            away_win_count=3,
            home_attendance_count=5,
            home_win_rate=60.0,
            away_win_rate=75.0,
            recent_10_attendance_count=9,
            recent_10_win_rate=66.67,
            weekday_stats=[],
        )
    )

    with patch(
        (
            "app.api.v1.endpoints.users."
            "AttendanceStatsService"
        ),
        return_value=service,
    ):
        response = authenticated_client.get(
            "/api/v1/users/me/attendance-stats"
        )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert body["data"]["awayTripCount"] == 4
    assert body["data"]["awayWinCount"] == 3
    assert body["data"]["homeWinRate"] == 60.0
    assert body["data"]["awayWinRate"] == 75.0
    assert (
        body["data"]["recent10WinRate"]
        == 66.67
    )

    kwargs = service.get_stats.call_args.kwargs

    assert kwargs["user_id"] == "firebase-user-123"
    assert (
        kwargs["current_support_team_id"]
        == "doosan"
    )


def test_attendance_stats_openapi_contract() -> None:
    schema = app.openapi()

    operation = schema["paths"][
        "/api/v1/users/me/attendance-stats"
    ]["get"]

    assert operation["summary"] == "내 직관 통계 조회"

    response_schema = schema[
        "components"
    ]["schemas"]["AttendanceStatsResponse"]

    properties = response_schema["properties"]

    expected = {
        "awayTripCount",
        "awayWinCount",
        "homeAttendanceCount",
        "homeWinRate",
        "awayWinRate",
        "recent10AttendanceCount",
        "recent10WinRate",
        "weekdayStats",
    }

    assert expected <= properties.keys()

    weekday_schema = schema[
        "components"
    ]["schemas"][
        "AttendanceWeekdayStatsResponse"
    ]

    weekday_properties = (
        weekday_schema["properties"]
    )

    assert {
        "weekday",
        "attendanceCount",
        "winCount",
        "lossCount",
        "drawCount",
        "winRate",
    } <= weekday_properties.keys()
