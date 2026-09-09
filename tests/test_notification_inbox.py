from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_current_active_user_id
from app.main import app
from app.repositories import notification_inbox_repository as repository_module
from app.repositories.notification_inbox_repository import (
    InvalidNotificationPageToken,
    NotificationInboxRepository,
)
from app.schemas.notification_inbox import NotificationRecord
from app.services.notification_inbox_service import NotificationInboxService


FIXED_TIME = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)


def make_record(
    notification_id: str = "notification_001",
    read_at: datetime | None = None,
) -> NotificationRecord:
    return NotificationRecord(
        notification_id=notification_id,
        type="TRIP_REMINDER",
        title="여행 일정 안내",
        body="여행 일정을 확인해 주세요.",
        created_at=FIXED_TIME,
        read_at=read_at,
        target_type="TRIP",
        target_id="trip_001",
    )


@pytest.fixture
def client():
    app.dependency_overrides[get_current_active_user_id] = (
        lambda: "user_test_1"
    )
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(
            get_current_active_user_id, None
        )


@pytest.fixture
def api_service():
    service = Mock(spec=NotificationInboxService)
    with patch(
        "app.api.v1.endpoints.notifications.NotificationInboxService",
        return_value=service,
    ):
        yield service


def test_empty_notification_list(client, api_service):
    api_service.get_notifications.return_value = ([], None)

    response = client.get("/api/v1/notifications")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == []
    assert body["meta"]["count"] == 0
    assert body["meta"]["nextPageToken"] is None

    api_service.get_notifications.assert_called_once_with(
        user_id="user_test_1",
        page_size=20,
        page_token=None,
    )


def test_notification_list_serializes_read_state(client, api_service):
    api_service.get_notifications.return_value = (
        [
            make_record("notification_002"),
            make_record("notification_001", read_at=FIXED_TIME),
        ],
        None,
    )

    response = client.get("/api/v1/notifications")

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 2
    assert data[0]["notificationId"] == "notification_002"
    assert data[0]["isRead"] is False
    assert data[0]["readAt"] is None
    assert data[1]["isRead"] is True
    assert data[1]["readAt"] is not None


def test_notification_list_forwards_pagination(client, api_service):
    api_service.get_notifications.return_value = (
        [make_record()],
        "notification_next",
    )

    response = client.get(
        "/api/v1/notifications",
        params={"pageSize": 2, "pageToken": "notification_cursor"},
    )

    assert response.status_code == 200
    assert response.json()["meta"]["nextPageToken"] == "notification_next"
    api_service.get_notifications.assert_called_once_with(
        user_id="user_test_1",
        page_size=2,
        page_token="notification_cursor",
    )


def test_invalid_page_size(client, api_service):
    response = client.get(
        "/api/v1/notifications",
        params={"pageSize": 0},
    )

    assert response.status_code == 422
    api_service.get_notifications.assert_not_called()


def test_invalid_page_token(client, api_service):
    api_service.get_notifications.side_effect = (
        InvalidNotificationPageToken()
    )

    response = client.get(
        "/api/v1/notifications",
        params={"pageToken": "missing"},
    )

    assert response.status_code == 400


def test_unread_count(client, api_service):
    api_service.get_unread_count.return_value = 3

    response = client.get("/api/v1/notifications/unread-count")

    assert response.status_code == 200
    assert response.json()["data"]["unreadCount"] == 3
    api_service.get_unread_count.assert_called_once_with(
        user_id="user_test_1"
    )


def test_mark_notification_read(client, api_service):
    api_service.mark_read.return_value = make_record(
        read_at=FIXED_TIME
    )

    response = client.patch(
        "/api/v1/notifications/notification_001/read"
    )

    assert response.status_code == 200
    assert response.json()["data"]["isRead"] is True
    api_service.mark_read.assert_called_once_with(
        user_id="user_test_1",
        notification_id="notification_001",
    )


def test_mark_missing_notification_returns_404(client, api_service):
    api_service.mark_read.return_value = None

    response = client.patch(
        "/api/v1/notifications/notification_missing/read"
    )

    assert response.status_code == 404


def make_repository():
    client = Mock()
    repository = NotificationInboxRepository(client=client)
    collection = (
        client.collection.return_value
        .document.return_value
        .collection.return_value
    )
    return repository, client, collection


def make_snapshot(notification_id, read_at=None):
    record = make_record(notification_id, read_at)
    return SimpleNamespace(
        id=notification_id,
        exists=True,
        to_dict=lambda: record.model_dump(
            by_alias=True,
            exclude={"notification_id"},
        ),
    )


def test_repository_paginates_and_scopes_to_user():
    repository, client, collection = make_repository()
    query = Mock()
    collection.order_by.return_value = query
    query.order_by.return_value = query
    query.limit.return_value = query
    query.stream.return_value = [
        make_snapshot("n3"),
        make_snapshot("n2"),
        make_snapshot("n1"),
    ]

    records, next_token = repository.get_page(
        user_id="user_test_1",
        page_size=2,
    )

    client.collection.assert_called_once_with("users")
    client.collection.return_value.document.assert_called_once_with(
        "user_test_1"
    )
    assert [record.notification_id for record in records] == ["n3", "n2"]
    assert next_token == "n2"
    query.limit.assert_called_once_with(3)


def test_repository_uses_cursor_from_same_user():
    repository, _, collection = make_repository()
    query = Mock()
    collection.order_by.return_value = query
    query.order_by.return_value = query
    query.start_after.return_value = query
    query.limit.return_value = query
    query.stream.return_value = []

    cursor = make_snapshot("n2")
    collection.document.return_value.get.return_value = cursor

    records, next_token = repository.get_page(
        user_id="user_test_1",
        page_size=2,
        page_token="n2",
    )

    collection.document.assert_called_once_with("n2")
    query.start_after.assert_called_once_with(cursor)
    assert records == []
    assert next_token is None


def test_repository_counts_unread_notifications():
    repository, _, collection = make_repository()
    query = collection.where.return_value
    aggregate = query.count.return_value
    aggregate.get.return_value = [
        [SimpleNamespace(value=3)]
    ]

    count = repository.get_unread_count(user_id="user_test_1")

    assert count == 3
    query.count.assert_called_once_with(alias="unreadCount")


def test_repository_mark_read_is_idempotent(monkeypatch):
    monkeypatch.setattr(
        repository_module.firestore,
        "transactional",
        lambda function: function,
    )

    repository, client, collection = make_repository()
    reference = collection.document.return_value
    transaction = client.transaction.return_value

    # 이미 읽은 알림은 기존 읽음 시간을 유지한다.
    reference.get.return_value = make_snapshot(
        "notification_001",
        read_at=FIXED_TIME,
    )

    record = repository.mark_read(
        user_id="user_test_1",
        notification_id="notification_001",
    )

    assert record.read_at == FIXED_TIME
    transaction.update.assert_not_called()

    # 읽지 않은 알림은 읽음 시간을 저장한다.
    reference.get.return_value = make_snapshot("notification_001")
    transaction.reset_mock()

    record = repository.mark_read(
        user_id="user_test_1",
        notification_id="notification_001",
    )

    assert record.read_at is not None
    transaction.update.assert_called_once()
    assert transaction.update.call_args.args[0] is reference
    assert "readAt" in transaction.update.call_args.args[1]
