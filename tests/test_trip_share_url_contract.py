from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import Response

from app.api.v1.endpoints import trip_shares


def test_share_url_uses_frontend_short_route(monkeypatch):
    monkeypatch.setattr(
        trip_shares,
        "settings",
        SimpleNamespace(share_web_origin="https://travel.example/"),
    )

    assert (
        trip_shares.build_share_url("sample-token")
        == "https://travel.example/s/sample-token"
    )


def test_share_url_is_none_without_web_origin(monkeypatch):
    monkeypatch.setattr(
        trip_shares,
        "settings",
        SimpleNamespace(share_web_origin=""),
    )

    assert trip_shares.build_share_url("sample-token") is None


def test_issue_share_returns_short_url(monkeypatch):
    token = "sample-share-token"
    created_at = datetime(
        2026, 9, 7, tzinfo=timezone.utc
    )

    monkeypatch.setattr(
        trip_shares,
        "settings",
        SimpleNamespace(share_web_origin="https://travel.example"),
    )
    monkeypatch.setattr(
        trip_shares,
        "TripShareService",
        lambda: SimpleNamespace(
            issue_with_metadata=lambda **kwargs: (
                token,
                created_at,
                None,
            )
        ),
    )

    response = Response()
    result = trip_shares.issue_trip_share(
        trip_id="trip_001",
        user_id="owner_001",
        response=response,
    )

    assert result.data.share_token == token
    assert result.data.share_url == (
        "https://travel.example/s/sample-share-token"
    )
    assert result.data.created_at == created_at
    assert result.data.revoked_at is None
    assert response.headers["Cache-Control"] == "no-store"
