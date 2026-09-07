from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.exceptions import AppException
from app.main import app
from app.schemas.notice import (
    NoticeDetailResponse,
    NoticeSummaryResponse,
)

client = TestClient(app)


def make_summary() -> NoticeSummaryResponse:
    return NoticeSummaryResponse(
        notice_id="notice_001",
        title="서비스 점검 안내",
        published_at=datetime(
            2026, 8, 15, 10, 0, tzinfo=timezone.utc
        ),
    )


def test_get_notices_returns_list_response() -> None:
    with patch(
        "app.api.v1.endpoints.notices.NoticeService"
    ) as service_class:
        service_class.return_value.get_notices.return_value = [
            make_summary()
        ]
        response = client.get("/api/v1/notices")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["meta"] == {
        "count": 1,
        "nextPageToken": None,
    }
    assert body["data"][0]["noticeId"] == "notice_001"
    assert "content" not in body["data"][0]


def test_get_notices_returns_empty_list() -> None:
    with patch(
        "app.api.v1.endpoints.notices.NoticeService"
    ) as service_class:
        service_class.return_value.get_notices.return_value = []
        response = client.get("/api/v1/notices")

    assert response.status_code == 200
    assert response.json()["data"] == []
    assert response.json()["meta"]["count"] == 0


def test_get_notice_returns_detail() -> None:
    summary = make_summary()
    notice = NoticeDetailResponse(
        **summary.model_dump(),
        content="서비스 점검이 진행됩니다.",
    )

    with patch(
        "app.api.v1.endpoints.notices.NoticeService"
    ) as service_class:
        get_notice = service_class.return_value.get_notice
        get_notice.return_value = notice
        response = client.get("/api/v1/notices/notice_001")

    assert response.status_code == 200
    assert response.json()["data"]["content"] == "서비스 점검이 진행됩니다."
    get_notice.assert_called_once_with("notice_001")


def test_get_notice_returns_common_404() -> None:
    with patch(
        "app.api.v1.endpoints.notices.NoticeService"
    ) as service_class:
        service_class.return_value.get_notice.side_effect = AppException(
            status_code=404,
            code="NOTICE_NOT_FOUND",
            message="공지사항을 찾을 수 없습니다.",
        )
        response = client.get("/api/v1/notices/missing")

    assert response.status_code == 404
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "NOTICE_NOT_FOUND"
