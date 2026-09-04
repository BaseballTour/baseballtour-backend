from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import (
    get_current_active_user_id,
)
from app.main import app
from app.schemas.itinerary_plan import (
    ItineraryPlanRecord,
    ItineraryPlanStatus,
)


USER_ID = "firebase-user-123"
TRIP_ID = "trip_001"
PLAN_ID = "plan_001"
ATTENDANCE_LOG_ID = "log_001"

NOW = datetime(
    2026,
    8,
    19,
    3,
    0,
    tzinfo=timezone.utc,
)


def make_plan() -> ItineraryPlanRecord:
    return ItineraryPlanRecord(
        plan_id=PLAN_ID,
        trip_id=TRIP_ID,
        user_id=USER_ID,
        status=ItineraryPlanStatus.ARCHIVED,
        algorithm_version="auto-fill-v0.4",
        total_travel_minutes=15,
        total_travel_distance_meters=1200,
        days=[
            {
                "date": "2026-08-15",
                "dayType": "GAME_DAY",
                "items": [
                    {
                        "itemId": "place_1",
                        "type": "PLACE",
                        "sequence": 1,
                        "placeId": "tour_001",
                        "category": "TOURIST_SPOT",
                        "thumbnailUrl": (
                            "https:"
                            "//example.com/gwangalli.jpg"
                        ),
                        "shortDescription": (
                            "부산을 대표하는 해변 관광지"
                        ),
                        "overview": (
                            "부산을 대표하는 해변 관광지입니다."
                        ),
                        "name": "광안리해수욕장",
                        "address": "부산광역시 수영구",
                        "latitude": 35.1532,
                        "longitude": 129.1187,
                        "scheduledStartAt": (
                            "2026-08-15T14:00:00+09:00"
                        ),
                        "scheduledEndAt": (
                            "2026-08-15T15:30:00+09:00"
                        ),
                        "travelMinutesFromPrevious": 15,
                        "travelDistanceMetersFromPrevious": 1200,
                        "travelMode": "TRANSIT",
                        "travelTimeSource": "KAKAO",
                        "isRequired": True,
                        "addedBy": "USER",
                    }
                ],
            }
        ],
        excluded_places=[],
        recommendation_summary=None,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.fixture
def authenticated_client() -> TestClient:
    app.dependency_overrides[
        get_current_active_user_id
    ] = lambda: USER_ID

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_get_attendance_log_itinerary_returns_saved_plan(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.get_itinerary.return_value = make_plan()

    with patch(
        (
            "app.api.v1.endpoints.attendance_logs."
            "AttendanceLogService"
        ),
        return_value=service,
    ):
        response = authenticated_client.get(
            (
                "/api/v1/attendance-logs/"
                f"{ATTENDANCE_LOG_ID}/itinerary"
            )
        )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True

    data = body["data"]

    assert data["planId"] == PLAN_ID
    assert data["tripId"] == TRIP_ID
    assert data["status"] == "ARCHIVED"
    assert data["algorithmVersion"] == "auto-fill-v0.4"
    assert data["totalTravelMinutes"] == 15
    assert data["totalTravelDistanceMeters"] == 1200

    item = data["days"][0]["items"][0]

    assert item["placeId"] == "tour_001"
    assert (
        item["thumbnailUrl"]
        == "https://example.com/gwangalli.jpg"
    )
    assert (
        item["shortDescription"]
        == "부산을 대표하는 해변 관광지"
    )
    assert (
        item["overview"]
        == "부산을 대표하는 해변 관광지입니다."
    )
    assert item["travelTimeSource"] == "KAKAO"

    assert "userId" not in data
    assert "createdAt" not in data
    assert "updatedAt" not in data

    service.get_itinerary.assert_called_once_with(
        user_id=USER_ID,
        attendance_log_id=ATTENDANCE_LOG_ID,
    )


def test_attendance_log_itinerary_is_get_only() -> None:
    target = (
        "/api/v1/attendance-logs/"
        "{attendanceLogId}/itinerary"
    )

    methods = {
        method.lower()
        for method in app.openapi()["paths"][target]
        if method.lower()
        in {
            "get",
            "post",
            "put",
            "patch",
            "delete",
            "options",
            "head",
        }
    }

    assert methods == {"get"}


def make_log_api_response():
    from app.schemas.attendance_log import (
        AttendanceLogResponse,
        AttendanceLogStatus,
    )

    return AttendanceLogResponse(
        attendance_log_id=ATTENDANCE_LOG_ID,
        trip_id=TRIP_ID,
        game_id="game_001",
        plan_id=PLAN_ID,
        log_title="부산 직관 여행",
        summary_text=None,
        log_status=AttendanceLogStatus.DRAFT,
        visibility="PRIVATE",
        created_at=NOW,
        updated_at=NOW,
    )


def make_log_detail_api_response():
    from app.schemas.attendance_log import (
        AttendanceLogDetailResponse,
        AttendanceLogStatus,
    )

    return AttendanceLogDetailResponse(
        attendance_log_id=ATTENDANCE_LOG_ID,
        trip_id=TRIP_ID,
        game_id="game_001",
        plan_id=PLAN_ID,
        log_title="부산 직관 여행",
        summary_text=None,
        log_status=AttendanceLogStatus.DRAFT,
        visibility="PRIVATE",
        created_at=NOW,
        updated_at=NOW,
        entries=[],
    )


def make_entry_api_response():
    from app.schemas.attendance_log import (
        LogEntryResponse,
        LogEntryType,
    )

    return LogEntryResponse(
        log_entry_id="entry_001",
        plan_item_id="place_001",
        place_id="tour_001",
        sequence_no=1,
        entry_type=LogEntryType.PLACE,
        entry_title="광안리해수욕장",
        review_text="좋았습니다.",
        occurred_at=NOW,
        media=[],
        created_at=NOW,
        updated_at=NOW,
    )


def test_create_attendance_log_api(
    authenticated_client: TestClient,
) -> None:
    from app.schemas.attendance_log import (
        AttendanceLogRecord,
        AttendanceLogStatus,
    )

    service = Mock()

    record = AttendanceLogRecord(
        attendance_log_id=ATTENDANCE_LOG_ID,
        user_id=USER_ID,
        trip_id=TRIP_ID,
        game_id="game_001",
        plan_id=PLAN_ID,
        log_title="직관 기록",
        summary_text=None,
        log_status=AttendanceLogStatus.DRAFT,
        visibility="PRIVATE",
        created_at=NOW,
        updated_at=NOW,
        deleted_at=None,
    )

    service.create_draft.return_value = record
    service.to_response.return_value = (
        make_log_api_response()
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
                "logTitle": "직관 기록",
            },
        )

    assert response.status_code == 201
    assert response.json()["success"] is True

    service.create_draft.assert_called_once_with(
        user_id=USER_ID,
        trip_id=TRIP_ID,
        log_title="직관 기록",
    )


def test_list_attendance_logs_api(
    authenticated_client: TestClient,
) -> None:
    from app.schemas.attendance_log import (
        AttendanceLogArchiveItemResponse,
        AttendanceLogGameResult,
        AttendanceLogHomeSide,
        AttendanceLogStatus,
        AttendanceLogVisibility,
    )

    service = Mock()
    service.list_archive_logs.return_value = (
        [
            AttendanceLogArchiveItemResponse(
                attendance_log_id=ATTENDANCE_LOG_ID,
                trip_id=TRIP_ID,
                game_id="game_001",
                plan_id=PLAN_ID,
                log_title="부산 직관 여행",
                summary_text="역전승 직관",
                game_start_at=NOW,
                stadium_name="사직야구장",
                home_team_name="롯데 자이언츠",
                away_team_name="두산 베어스",
                home_score=3,
                away_score=5,
                home_side=AttendanceLogHomeSide.AWAY,
                result=AttendanceLogGameResult.WIN,
                cover_image_url=(
                    "https://example.com/cover.jpg"
                ),
                log_status=AttendanceLogStatus.DRAFT,
                visibility=(
                    AttendanceLogVisibility.PRIVATE
                ),
                created_at=NOW,
                updated_at=NOW,
            )
        ],
        "next-token",
    )

    with patch(
        (
            "app.api.v1.endpoints.attendance_logs."
            "AttendanceLogService"
        ),
        return_value=service,
    ):
        response = authenticated_client.get(
            (
                "/api/v1/attendance-logs"
                "?pageSize=5&pageToken=cursor123"
            )
        )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert body["meta"] == {
        "count": 1,
        "nextPageToken": "next-token",
    }

    item = body["data"][0]

    assert (
        item["attendanceLogId"]
        == ATTENDANCE_LOG_ID
    )
    assert item["stadiumName"] == "사직야구장"
    assert item["homeTeamName"] == "롯데 자이언츠"
    assert item["awayTeamName"] == "두산 베어스"
    assert item["homeScore"] == 3
    assert item["awayScore"] == 5
    assert item["homeSide"] == "AWAY"
    assert item["result"] == "WIN"
    assert item["summaryText"] == "역전승 직관"
    assert (
        item["coverImageUrl"]
        == "https://example.com/cover.jpg"
    )

    service.list_archive_logs.assert_called_once_with(
        user_id=USER_ID,
        page_size=5,
        page_token="cursor123",
    )

def test_get_attendance_log_detail_api(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.get_detail.return_value = (
        make_log_detail_api_response()
    )

    with patch(
        (
            "app.api.v1.endpoints.attendance_logs."
            "AttendanceLogService"
        ),
        return_value=service,
    ):
        response = authenticated_client.get(
            (
                "/api/v1/attendance-logs/"
                f"{ATTENDANCE_LOG_ID}"
            )
        )

    assert response.status_code == 200

    assert (
        response.json()["data"]["attendanceLogId"]
        == ATTENDANCE_LOG_ID
    )

    service.get_detail.assert_called_once_with(
        user_id=USER_ID,
        attendance_log_id=ATTENDANCE_LOG_ID,
    )


def test_update_attendance_log_api(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.update_log.return_value = (
        make_log_api_response()
    )

    with patch(
        (
            "app.api.v1.endpoints.attendance_logs."
            "AttendanceLogService"
        ),
        return_value=service,
    ):
        response = authenticated_client.patch(
            (
                "/api/v1/attendance-logs/"
                f"{ATTENDANCE_LOG_ID}"
            ),
            json={
                "summaryText": "역전승 직관",
            },
        )

    assert response.status_code == 200

    kwargs = (
        service.update_log.call_args.kwargs
    )

    assert kwargs["user_id"] == USER_ID
    assert (
        kwargs["attendance_log_id"]
        == ATTENDANCE_LOG_ID
    )
    assert (
        kwargs["request"].summary_text
        == "역전승 직관"
    )


def test_update_attendance_log_entry_api(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.update_entry.return_value = (
        make_entry_api_response()
    )

    with patch(
        (
            "app.api.v1.endpoints.attendance_logs."
            "AttendanceLogService"
        ),
        return_value=service,
    ):
        response = authenticated_client.patch(
            (
                "/api/v1/attendance-logs/"
                f"{ATTENDANCE_LOG_ID}/"
                "entries/entry_001"
            ),
            json={
                "reviewText": "정말 좋았습니다.",
            },
        )

    assert response.status_code == 200

    kwargs = (
        service.update_entry.call_args.kwargs
    )

    assert kwargs["user_id"] == USER_ID
    assert kwargs["log_entry_id"] == "entry_001"


def test_delete_attendance_log_api(
    authenticated_client: TestClient,
) -> None:
    service = Mock()

    with patch(
        (
            "app.api.v1.endpoints.attendance_logs."
            "AttendanceLogService"
        ),
        return_value=service,
    ):
        response = authenticated_client.delete(
            (
                "/api/v1/attendance-logs/"
                f"{ATTENDANCE_LOG_ID}"
            )
        )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "deleted": True
    }

    service.delete_log.assert_called_once_with(
        user_id=USER_ID,
        attendance_log_id=ATTENDANCE_LOG_ID,
    )


def test_delete_attendance_log_media_api(
    authenticated_client: TestClient,
) -> None:
    service = Mock()

    with patch(
        (
            "app.api.v1.endpoints.attendance_logs."
            "AttendanceLogService"
        ),
        return_value=service,
    ):
        response = authenticated_client.delete(
            (
                "/api/v1/attendance-logs/"
                f"{ATTENDANCE_LOG_ID}/"
                "entries/entry_001/"
                "media/media_001"
            )
        )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "deleted": True
    }

    service.delete_media.assert_called_once_with(
        user_id=USER_ID,
        attendance_log_id=ATTENDANCE_LOG_ID,
        log_entry_id="entry_001",
        log_media_id="media_001",
    )


def test_update_attendance_log_seat_api(
    authenticated_client: TestClient,
) -> None:
    service = Mock()

    service.update_log.return_value = (
        make_log_api_response().model_copy(
            update={
                "seat": "3루 내야 B블록 15열",
            }
        )
    )

    with patch(
        (
            "app.api.v1.endpoints.attendance_logs."
            "AttendanceLogService"
        ),
        return_value=service,
    ):
        response = authenticated_client.patch(
            (
                "/api/v1/attendance-logs/"
                f"{ATTENDANCE_LOG_ID}"
            ),
            json={
                "seat": "3루 내야 B블록 15열",
            },
        )

    assert response.status_code == 200

    assert (
        response.json()["data"]["seat"]
        == "3루 내야 B블록 15열"
    )

    request = (
        service.update_log.call_args
        .kwargs["request"]
    )

    assert (
        request.seat
        == "3루 내야 B블록 15열"
    )
