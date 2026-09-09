import json
from datetime import date, datetime, timezone
from types import SimpleNamespace

from app.models.itinerary import DayType, ItineraryItemType
from app.schemas.game import (
    GameResponse,
    GameStatus,
    GameTeamSummaryResponse,
)
from app.schemas.itinerary_plan import (
    ItineraryPlanDay,
    ItineraryPlanItem,
    ItineraryPlanRecord,
    ItineraryPlanStatus,
)
from app.schemas.stadium import StadiumSummaryResponse
from app.services.trip_share_public import (
    resolve_shared_subtitle,
    to_shared_trip,
)


NOW = datetime(2026, 8, 15, 9, 0, tzinfo=timezone.utc)


def make_item(
    *,
    item_id: str,
    item_type: ItineraryItemType,
    sequence: int,
    name: str,
    address: str,
):
    return ItineraryPlanItem.model_construct(
        item_id=item_id,
        is_fixed=False,
        item_type=item_type,
        sequence=sequence,
        place_id="secret-place-id",
        place_url="https://example.com/secret",
        name=name,
        address=address,
        latitude=35.1,
        longitude=129.1,
        scheduled_start_at=NOW,
        scheduled_end_at=NOW,
        travel_minutes_from_previous=0,
        travel_distance_meters_from_previous=0,
        transfer_buffer_minutes=0,
        is_required=True,
    )


def make_plan():
    return ItineraryPlanRecord.model_construct(
        plan_id="plan-secret-001",
        trip_id="trip-secret-001",
        user_id="user-secret-001",
        status=ItineraryPlanStatus.ACTIVE,
        algorithm_version="test",
        total_travel_minutes=30,
        total_travel_distance_meters=1000,
        days=[
            ItineraryPlanDay.model_construct(
                date=date(2026, 8, 15),
                day_type=DayType.GAME_DAY,
                items=[
                    make_item(
                        item_id="item-accommodation",
                        item_type=ItineraryItemType.ACCOMMODATION,
                        sequence=1,
                        name="비밀 호텔",
                        address="공개되면 안 되는 숙소 주소",
                    ),
                    make_item(
                        item_id="item-place",
                        item_type=ItineraryItemType.PLACE,
                        sequence=2,
                        name="광안리해수욕장",
                        address="부산광역시 수영구",
                    ),
                ],
            )
        ],
        excluded_places=[],
        recommendation_summary=None,
        created_at=NOW,
        updated_at=NOW,
    )


def make_game():
    return GameResponse(
        game_id="game_001",
        game_start_at=NOW,
        status=GameStatus.SCHEDULED,
        home_team=GameTeamSummaryResponse(
            team_id="lotte",
            name="롯데 자이언츠",
            logo_url=None,
        ),
        away_team=GameTeamSummaryResponse(
            team_id="doosan",
            name="두산 베어스",
            logo_url=None,
        ),
        stadium=StadiumSummaryResponse(
            stadium_id="sajik",
            name="사직야구장",
            address="부산광역시 동래구 사직로 45",
            latitude=35.194,
            longitude=129.0615,
        ),
    )


def test_shared_trip_removes_internal_ids_and_accommodation_details():
    trip = SimpleNamespace(
        trip_id="trip-secret-001",
        user_id="user-secret-001",
        game_id="game_001",
        title="부산 원정",
        subtitle=None,
        trip_start_at=datetime(
            2026, 8, 15, 3, 0, tzinfo=timezone.utc
        ),
        trip_end_at=datetime(
            2026, 8, 16, 3, 0, tzinfo=timezone.utc
        ),
        accommodation=SimpleNamespace(
            accommodation_id="accommodation-secret",
            name="비밀 호텔",
            address="공개되면 안 되는 숙소 주소",
            latitude=35.123,
            longitude=129.123,
            place_url="https://example.com/private",
        ),
    )

    response = to_shared_trip(
        trip=trip,
        plan=make_plan(),
        game=make_game(),
        subtitle=resolve_shared_subtitle(trip),
    )

    payload = response.model_dump(mode="json", by_alias=True)
    serialized = json.dumps(payload, ensure_ascii=False)

    assert "trip-secret-001" not in serialized
    assert "plan-secret-001" not in serialized
    assert "user-secret-001" not in serialized

    assert payload["accommodation"] == {
        "name": "비밀 호텔",
    }

    accommodation_item = payload["plan"]["days"][0]["items"][0]
    assert accommodation_item == {
        "type": "ACCOMMODATION",
        "sequence": 1,
        "name": "비밀 호텔",
    }

    place_item = payload["plan"]["days"][0]["items"][1]
    assert place_item["type"] == "PLACE"
    assert place_item["address"] == "부산광역시 수영구"

    assert "공개되면 안 되는 숙소 주소" not in serialized
    assert "accommodation-secret" not in serialized
    assert "https://example.com/private" not in serialized


def test_shared_subtitle_uses_korea_dates():
    trip = SimpleNamespace(
        subtitle=None,
        trip_start_at=datetime(
            2026, 8, 15, 14, 30, tzinfo=timezone.utc
        ),
        trip_end_at=datetime(
            2026, 8, 16, 15, 30, tzinfo=timezone.utc
        ),
    )

    assert resolve_shared_subtitle(trip) == (
        "2026.08.15 ~ 2026.08.17"
    )


def test_shared_subtitle_preserves_custom_value():
    trip = SimpleNamespace(
        subtitle="부산 야구 여행",
        trip_start_at=NOW,
        trip_end_at=NOW,
    )

    assert resolve_shared_subtitle(trip) == "부산 야구 여행"
