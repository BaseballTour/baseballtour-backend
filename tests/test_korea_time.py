from datetime import datetime, timezone

from app.schemas.trip import TripStatus, TripSummaryResponse


def test_api_model_normalizes_and_serializes_utc_as_korea_time() -> None:
    response = TripSummaryResponse(
        trip_id="trip_1",
        game_id="game_1",
        title="한국시간 테스트",
        subtitle="2026.08.18",
        status=TripStatus.PLANNING,
        trip_start_at=datetime(2026, 8, 18, 3, tzinfo=timezone.utc),
        trip_end_at=datetime(2026, 8, 18, 14, tzinfo=timezone.utc),
        created_at=datetime(2026, 8, 18, 1, tzinfo=timezone.utc),
    )

    assert response.trip_start_at.isoformat() == "2026-08-18T12:00:00+09:00"
    payload = response.model_dump_json(by_alias=True)
    assert '"tripStartAt":"2026-08-18T12:00:00+09:00"' in payload
    assert '"createdAt":"2026-08-18T10:00:00+09:00"' in payload
