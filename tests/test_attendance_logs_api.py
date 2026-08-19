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
    AttendanceLogVisibility,
    LogEntryRecord,
    LogEntryType,
    LogMediaRecord,
    LogMediaType,
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
        "visibility": "PRIVATE",
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


def make_entry_record(
    *,
    log_entry_id: str = "entry_001",
    sequence_no: int = 1,
) -> LogEntryRecord:
    return LogEntryRecord(
        log_entry_id=log_entry_id,
        plan_item_id="item_001",
        place_id="tour_001",
        sequence_no=sequence_no,
        entry_type=LogEntryType.PLACE,
        entry_title="광안리해수욕장",
        review_text=None,
        occurred_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )


def test_get_my_attendance_logs_returns_list(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.get_my_logs.return_value = [
        make_log_record(),
    ]

    with patch(
        (
            "app.api.v1.endpoints.attendance_logs."
            "AttendanceLogService"
        ),
        return_value=service,
    ):
        response = authenticated_client.get(
            "/api/v1/attendance-logs"
        )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert len(body["data"]) == 1
    assert body["data"][0]["attendanceLogId"] == "log_001"

    assert body["meta"] == {
        "count": 1,
        "nextPageToken": None,
    }

    service.get_my_logs.assert_called_once_with(
        user_id=USER_ID,
    )


def test_get_attendance_log_detail_returns_entries(
    authenticated_client: TestClient,
) -> None:
    service = Mock()

    service.get_log_detail_with_media.return_value = (
        make_log_record(),
        [
            make_entry_record(),
        ],
        {
            "entry_001": [
                LogMediaRecord(
                    log_media_id="media_001",
                    media_type=LogMediaType.IMAGE,
                    media_url=(
                        "https://example.com/photo.jpg"
                    ),
                    thumbnail_url=None,
                    sequence_no=1,
                    created_at=NOW,
                ),
            ],
        },
    )

    with patch(
        (
            "app.api.v1.endpoints.attendance_logs."
            "AttendanceLogService"
        ),
        return_value=service,
    ):
        response = authenticated_client.get(
            "/api/v1/attendance-logs/log_001"
        )

    assert response.status_code == 200

    data = response.json()["data"]

    assert data["attendanceLogId"] == "log_001"
    assert len(data["entries"]) == 1

    entry = data["entries"][0]

    assert entry["logEntryId"] == "entry_001"
    assert entry["planItemId"] == "item_001"
    assert entry["placeId"] == "tour_001"
    assert entry["sequenceNo"] == 1
    assert entry["entryType"] == "PLACE"

    assert entry["media"] == [
        {
            "logMediaId": "media_001",
            "mediaType": "IMAGE",
            "mediaUrl": (
                "https://example.com/photo.jpg"
            ),
            "thumbnailUrl": None,
            "sequenceNo": 1,
            "createdAt": (
                "2026-08-19T03:00:00Z"
            ),
        }
    ]

    service.get_log_detail_with_media.assert_called_once_with(
        user_id=USER_ID,
        attendance_log_id="log_001",
    )


def test_update_attendance_log_returns_updated_log(
    authenticated_client: TestClient,
) -> None:
    service = Mock()

    service.update_log.return_value = (
        make_log_record(
            log_title="수정된 사직 직관 기록",
        ).model_copy(
            update={
                "summary_text": "정말 재미있었던 경기",
                "log_status": (
                    AttendanceLogStatus.PUBLISHED
                ),
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
            "/api/v1/attendance-logs/log_001",
            json={
                "logTitle": "수정된 사직 직관 기록",
                "summaryText": "정말 재미있었던 경기",
                "logStatus": "PUBLISHED",
            },
        )

    assert response.status_code == 200

    data = response.json()["data"]

    assert data["attendanceLogId"] == "log_001"
    assert data["logTitle"] == (
        "수정된 사직 직관 기록"
    )
    assert data["summaryText"] == (
        "정말 재미있었던 경기"
    )
    assert data["logStatus"] == "PUBLISHED"

    service.update_log.assert_called_once()

    arguments = service.update_log.call_args.kwargs

    assert arguments["user_id"] == USER_ID
    assert arguments["attendance_log_id"] == "log_001"
    assert arguments["request"].log_title == (
        "수정된 사직 직관 기록"
    )
    assert (
        arguments["request"].log_status
        == AttendanceLogStatus.PUBLISHED
    )


def test_update_attendance_log_rejects_empty_body(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.patch(
        "/api/v1/attendance-logs/log_001",
        json={},
    )

    assert response.status_code == 422

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_delete_attendance_log_returns_no_content(
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
            "/api/v1/attendance-logs/log_001"
        )

    assert response.status_code == 204
    assert response.content == b""

    service.delete_log.assert_called_once_with(
        user_id=USER_ID,
        attendance_log_id="log_001",
    )


def test_create_log_media_returns_created_media(
    authenticated_client: TestClient,
) -> None:
    service = Mock()

    service.create_media.return_value = (
        LogMediaRecord(
            log_media_id="media_001",
            media_type=LogMediaType.IMAGE,
            media_url=(
                "https://example.com/photo.jpg"
            ),
            thumbnail_url=None,
            sequence_no=1,
            created_at=NOW,
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
            (
                "/api/v1/attendance-logs/log_001/"
                "entries/entry_001/media"
            ),
            json={
                "mediaType": "IMAGE",
                "mediaUrl": (
                    "https://example.com/photo.jpg"
                ),
                "thumbnailUrl": None,
                "sequenceNo": 1,
            },
        )

    assert response.status_code == 201

    data = response.json()["data"]

    assert data == {
        "logMediaId": "media_001",
        "mediaType": "IMAGE",
        "mediaUrl": (
            "https://example.com/photo.jpg"
        ),
        "thumbnailUrl": None,
        "sequenceNo": 1,
        "createdAt": "2026-08-19T03:00:00Z",
    }

    service.create_media.assert_called_once()

    arguments = (
        service.create_media.call_args.kwargs
    )

    assert arguments["user_id"] == USER_ID
    assert (
        arguments["attendance_log_id"]
        == "log_001"
    )
    assert (
        arguments["log_entry_id"]
        == "entry_001"
    )
    assert (
        arguments["request"].media_type
        == LogMediaType.IMAGE
    )
    assert (
        arguments["request"].media_url
        == "https://example.com/photo.jpg"
    )
    assert arguments["request"].sequence_no == 1


def test_create_log_media_validates_sequence_no(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.post(
        (
            "/api/v1/attendance-logs/log_001/"
            "entries/entry_001/media"
        ),
        json={
            "mediaType": "IMAGE",
            "mediaUrl": (
                "https://example.com/photo.jpg"
            ),
            "sequenceNo": 0,
        },
    )

    assert response.status_code == 422

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == (
        "VALIDATION_ERROR"
    )


def test_delete_log_media_returns_no_content(
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
                "/api/v1/attendance-logs/log_001/"
                "entries/entry_001/media/media_001"
            )
        )

    assert response.status_code == 204
    assert response.content == b""

    service.delete_media.assert_called_once_with(
        user_id=USER_ID,
        attendance_log_id="log_001",
        log_entry_id="entry_001",
        log_media_id="media_001",
    )


def test_update_game_entry_review_returns_updated_entry(
    authenticated_client: TestClient,
) -> None:
    service = Mock()

    updated_entry = LogEntryRecord(
        log_entry_id="entry_game",
        plan_item_id="stadium",
        place_id=None,
        sequence_no=2,
        entry_type=LogEntryType.GAME,
        entry_title="사직야구장",
        review_text="끝내기 승리라 정말 짜릿했다.",
        occurred_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )

    service.update_entry.return_value = (
        updated_entry,
        [],
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
                "/api/v1/attendance-logs/log_001/"
                "entries/entry_game"
            ),
            json={
                "reviewText": (
                    "끝내기 승리라 정말 짜릿했다."
                )
            },
        )

    assert response.status_code == 200

    data = response.json()["data"]

    assert data["logEntryId"] == "entry_game"
    assert data["entryType"] == "GAME"
    assert data["reviewText"] == (
        "끝내기 승리라 정말 짜릿했다."
    )
    assert data["media"] == []

    service.update_entry.assert_called_once()

    arguments = (
        service.update_entry.call_args.kwargs
    )

    assert arguments["user_id"] == USER_ID
    assert (
        arguments["attendance_log_id"]
        == "log_001"
    )
    assert (
        arguments["log_entry_id"]
        == "entry_game"
    )
    assert arguments["request"].review_text == (
        "끝내기 승리라 정말 짜릿했다."
    )


def test_update_log_entry_rejects_empty_body(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.patch(
        (
            "/api/v1/attendance-logs/log_001/"
            "entries/entry_game"
        ),
        json={},
    )

    assert response.status_code == 422

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == (
        "VALIDATION_ERROR"
    )


def test_update_attendance_log_visibility(
    authenticated_client: TestClient,
) -> None:
    service = Mock()

    service.update_log.return_value = (
        make_log_record().model_copy(
            update={
                "visibility": (
                    AttendanceLogVisibility.PUBLIC
                ),
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
            "/api/v1/attendance-logs/log_001",
            json={
                "visibility": "PUBLIC",
            },
        )

    assert response.status_code == 200

    data = response.json()["data"]

    assert data["visibility"] == "PUBLIC"

    arguments = (
        service.update_log.call_args.kwargs
    )

    assert (
        arguments["request"].visibility
        == AttendanceLogVisibility.PUBLIC
    )


def test_update_game_entry_rating(
    authenticated_client: TestClient,
) -> None:
    service = Mock()

    entry = make_entry_record().model_copy(
        update={
            "log_entry_id": "entry_game",
            "entry_type": LogEntryType.GAME,
            "place_id": None,
            "rating": 5,
        }
    )

    service.update_entry.return_value = (
        entry,
        [],
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
                "/api/v1/attendance-logs/log_001/"
                "entries/entry_game"
            ),
            json={
                "rating": 5,
            },
        )

    assert response.status_code == 200

    data = response.json()["data"]

    assert data["entryType"] == "GAME"
    assert data["rating"] == 5

    arguments = (
        service.update_entry.call_args.kwargs
    )

    assert arguments["request"].rating == 5
