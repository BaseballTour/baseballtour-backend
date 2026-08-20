import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.exceptions import AppException
from app.models.itinerary import (
    ItineraryDay,
    ItineraryItem,
    ItineraryItemAddedBy,
    ItineraryItemType,
    ItineraryResult,
)
from app.models.place import Place, PlaceCategory, PlaceSource
from app.schemas.itinerary_plan import (
    ItineraryPlanRecord,
    ItineraryPlanStatus,
)
from app.schemas.trip import TripRecord, TripStatus
from app.services.itinerary_generation_service import (
    ItineraryGenerationService,
)


USER_ID = "firebase-user-123"
TRIP_ID = "trip_001"

START_AT = datetime.fromisoformat(
    "2026-08-15T12:00:00+09:00"
)
END_AT = datetime.fromisoformat(
    "2026-08-15T23:00:00+09:00"
)
GAME_AT = datetime.fromisoformat(
    "2026-08-15T18:00:00+09:00"
)

NOW = datetime(
    2026,
    8,
    12,
    14,
    0,
    tzinfo=timezone.utc,
)



@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def make_trip(
    *,
    user_id: str = USER_ID,
    trip_status: TripStatus = TripStatus.PLANNING,
    active_plan_id: str | None = None,
    arrival=True,
    departure=True,
    rejected_recommendation_place_ids=None,
) -> TripRecord:
    return TripRecord(
        trip_id=TRIP_ID,
        user_id=user_id,
        game_id="game_001",
        title="부산 직관 여행",
        trip_start_at=START_AT,
        trip_end_at=END_AT,
        arrival_point=(
            {
                "name": "부산역",
                "latitude": 35.1151,
                "longitude": 129.0414,
            }
            if arrival
            else None
        ),
        departure_point=(
            {
                "name": "부산역",
                "latitude": 35.1151,
                "longitude": 129.0414,
            }
            if departure
            else None
        ),
        accommodation=None,
        status=trip_status,
        active_plan_id=active_plan_id,
        rejected_recommendation_place_ids=(
            rejected_recommendation_place_ids or []
        ),
        created_at=NOW,
        updated_at=NOW,
    )


def make_game():
    return SimpleNamespace(
        game_id="game_001",
        stadium_id="sajik",
        game_start_at=GAME_AT,
    )


def make_stadium():
    return SimpleNamespace(
        stadium_id="sajik",
        name="사직야구장",
        address="부산광역시 동래구 사직로 45",
        latitude=35.194,
        longitude=129.0615,
    )


def make_result() -> ItineraryResult:
    item = ItineraryItem(
        type=ItineraryItemType.STADIUM,
        sequence=1,
        place_id="sajik",
        name="사직야구장",
        address="부산광역시 동래구 사직로 45",
        latitude=35.194,
        longitude=129.0615,
        scheduled_start_at=datetime.fromisoformat(
            "2026-08-15T17:20:00+09:00"
        ),
        scheduled_end_at=datetime.fromisoformat(
            "2026-08-15T21:00:00+09:00"
        ),
        travel_minutes_from_previous=0,
        travel_time_source=None,
        is_required=True,
    )

    return ItineraryResult(
        trip_id=TRIP_ID,
        algorithm_version="greedy-anchor-v0.1",
        total_travel_minutes=0,
        days=[
            ItineraryDay(
                date=START_AT.date(),
                day_type="GAME_DAY",
                items=[item],
            )
        ],
        excluded_places=[],
    )


def make_service(
    *,
    trip=None,
    game=None,
    stadium=None,
    selections=None,
    generator=None,
    recommendations=None,
):
    trip_repository = Mock()

    source_trip = (
        trip if trip is not None else make_trip()
    )

    trip_repository.get_by_id.return_value = source_trip

    trip_repository.claim_generation.side_effect = (
        lambda **kwargs: source_trip.model_copy(
            update={
                "status": TripStatus.GENERATING,
                "updated_at": kwargs["updated_at"],
            }
        )
    )

    trip_repository.update.side_effect = (
        lambda trip_id, updates: make_trip(
            trip_status=TripStatus(
                updates.get(
                    "status",
                    TripStatus.PLANNING.value,
                )
            )
        )
    )

    game_repository = Mock()
    game_repository.get_by_id.return_value = (
        game if game is not None else make_game()
    )

    stadium_repository = Mock()
    stadium_repository.get_by_id.return_value = (
        stadium
        if stadium is not None
        else make_stadium()
    )

    selection_repository = Mock()
    selection_repository.get_all.return_value = (
        selections if selections is not None else []
    )

    plan_repository = Mock()
    plan_repository.get_by_id.return_value = None

    plan_repository.commit_generated_plan.side_effect = (
        lambda **kwargs: ItineraryPlanRecord(
            plan_id="plan_001",
            **kwargs["plan"].model_dump(),
        )
    )

    place_adapter = Mock()
    place_adapter.get_place_detail = AsyncMock()

    recommendation_service = Mock()
    recommendation_service.get_candidates = AsyncMock(
        return_value=(
            recommendations
            if recommendations is not None
            else []
        )
    )

    service = ItineraryGenerationService(
        trip_repository=trip_repository,
        game_repository=game_repository,
        stadium_repository=stadium_repository,
        place_selection_repository=selection_repository,
        itinerary_plan_repository=plan_repository,
        place_adapter=place_adapter,
        recommendation_service=recommendation_service,
        travel_time_provider=None,
        generator=generator or (lambda *_, **__: make_result()),
    )

    return SimpleNamespace(
        service=service,
        trip_repository=trip_repository,
        game_repository=game_repository,
        stadium_repository=stadium_repository,
        selection_repository=selection_repository,
        plan_repository=plan_repository,
        place_adapter=place_adapter,
        recommendation_service=recommendation_service,
    )


@pytest.mark.anyio
async def test_generate_saves_active_plan() -> None:
    context = make_service()

    result = await context.service.generate(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    )

    assert result.plan_id == "plan_001"
    assert result.status == ItineraryPlanStatus.ACTIVE
    assert result.days[0].items[0].item_id == "item_1_1"

    updates = context.trip_repository.update.call_args_list

    context.trip_repository.claim_generation.assert_called_once()

    context.plan_repository.commit_generated_plan.assert_called_once()

    arguments = (
        context.plan_repository
        .commit_generated_plan
        .call_args.kwargs
    )

    assert arguments["trip_id"] == TRIP_ID
    assert arguments["previous_plan_id"] is None
    assert arguments["plan"].trip_id == TRIP_ID
    assert arguments["plan"].user_id == USER_ID


@pytest.mark.anyio
async def test_generate_supplies_real_recommendation_candidates() -> None:
    recommendation = Place(
        place_id="tour_987654",
        name="추천 관광지",
        category=PlaceCategory.TOURIST_SPOT,
        latitude=35.18,
        longitude=129.07,
        source=PlaceSource.TOUR_API,
        source_content_id="987654",
    )
    generator = Mock(return_value=make_result())
    context = make_service(
        generator=generator,
        recommendations=[recommendation],
    )

    await context.service.generate(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    )

    request = context.recommendation_service.get_candidates.await_args.kwargs
    assert set(request["selected_place_ids"]) == set()
    assert len(request["centers"]) == 2
    assert request["centers"][0].latitude == 35.194
    assert request["centers"][1].latitude == 35.1151

    generator.assert_called_once()
    assert generator.call_args.kwargs["recommended_places"] == [
        recommendation
    ]
    matrix = generator.call_args.args[2]
    assert any(
        "tour_987654" in route
        for route in matrix.minutes
    )


@pytest.mark.anyio
async def test_generate_passes_previous_active_plan() -> None:
    context = make_service(
        trip=make_trip(
            trip_status=TripStatus.GENERATED,
            active_plan_id="plan_old",
        )
    )

    await context.service.generate(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    )

    arguments = (
        context.plan_repository
        .commit_generated_plan
        .call_args.kwargs
    )

    assert arguments["previous_plan_id"] == "plan_old"


@pytest.mark.anyio
async def test_regenerate_excludes_previous_unfixed_recommendations() -> None:
    context = make_service(
        trip=make_trip(
            trip_status=TripStatus.GENERATED,
            active_plan_id="plan_old",
            rejected_recommendation_place_ids=["tour_older_rejected"],
        )
    )
    context.plan_repository.get_by_id.return_value = SimpleNamespace(
        days=[
            SimpleNamespace(
                items=[
                    SimpleNamespace(
                        item_type=ItineraryItemType.PLACE,
                        place_id="tour_rejected",
                        added_by=ItineraryItemAddedBy.ALGORITHM,
                        is_fixed=False,
                    ),
                    SimpleNamespace(
                        item_type=ItineraryItemType.PLACE,
                        place_id="tour_fixed",
                        added_by=ItineraryItemAddedBy.ALGORITHM,
                        is_fixed=True,
                    ),
                    SimpleNamespace(
                        item_type=ItineraryItemType.PLACE,
                        place_id="tour_user",
                        added_by=ItineraryItemAddedBy.USER,
                        is_fixed=False,
                    ),
                ]
            )
        ]
    )

    await context.service.generate(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    )

    request = context.recommendation_service.get_candidates.await_args.kwargs
    assert set(request["selected_place_ids"]) == {
        "tour_older_rejected",
        "tour_rejected",
    }
    commit_request = (
        context.plan_repository.commit_generated_plan.call_args.kwargs
    )
    assert commit_request["rejected_recommendation_place_ids"] == [
        "tour_older_rejected",
        "tour_rejected",
    ]


@pytest.mark.anyio
async def test_generate_rejects_missing_trip() -> None:
    context = make_service()
    context.trip_repository.get_by_id.return_value = None

    with pytest.raises(AppException) as captured:
        await context.service.generate(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.status_code == 404
    assert captured.value.code == "TRIP_NOT_FOUND"


@pytest.mark.anyio
async def test_generate_rejects_other_user_trip() -> None:
    context = make_service(
        trip=make_trip(
            user_id="another-user",
        )
    )

    with pytest.raises(AppException) as captured:
        await context.service.generate(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.status_code == 403
    assert captured.value.code == "TRIP_ACCESS_DENIED"


@pytest.mark.anyio
async def test_generate_rejects_generation_in_progress() -> None:
    context = make_service(
        trip=make_trip(
            trip_status=TripStatus.GENERATING,
        )
    )

    with pytest.raises(AppException) as captured:
        await context.service.generate(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.status_code == 409
    assert captured.value.code == (
        "TRIP_GENERATION_IN_PROGRESS"
    )

    context.trip_repository.claim_generation.assert_not_called()
    context.trip_repository.update.assert_not_called()


@pytest.mark.anyio
async def test_generate_requires_arrival_and_departure() -> None:
    context = make_service(
        trip=make_trip(
            arrival=False,
            departure=False,
        )
    )

    with pytest.raises(AppException) as captured:
        await context.service.generate(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.status_code == 400
    assert captured.value.code == "TRIP_POINTS_REQUIRED"
    assert captured.value.details == {
        "missingFields": [
            "arrivalPoint",
            "departurePoint",
        ]
    }


@pytest.mark.anyio
async def test_generate_restores_status_when_game_missing() -> None:
    context = make_service()
    context.game_repository.get_by_id.return_value = None

    with pytest.raises(AppException) as captured:
        await context.service.generate(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.code == "GAME_NOT_FOUND"

    updates = context.trip_repository.update.call_args_list

    context.trip_repository.claim_generation.assert_called_once()
    assert updates[-1].args[1]["status"] == "PLANNING"


@pytest.mark.anyio
async def test_generate_restores_generated_status_on_regeneration_failure() -> None:
    context = make_service(
        trip=make_trip(
            trip_status=TripStatus.GENERATED,
            active_plan_id="plan_old",
        )
    )

    context.stadium_repository.get_by_id.return_value = None

    with pytest.raises(AppException) as captured:
        await context.service.generate(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.code == "STADIUM_NOT_FOUND"

    updates = context.trip_repository.update.call_args_list

    context.trip_repository.claim_generation.assert_called_once()
    assert updates[-1].args[1]["status"] == "GENERATED"


@pytest.mark.anyio
async def test_generate_continues_without_recommendations_after_timeout() -> None:
    generator = Mock(return_value=make_result())
    context = make_service(generator=generator)
    context.recommendation_service.get_candidates.side_effect = (
        asyncio.TimeoutError
    )

    result = await context.service.generate(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    )

    assert result.plan_id == "plan_001"
    assert generator.call_args.kwargs["recommended_places"] == []


@pytest.mark.anyio
async def test_generate_restores_status_when_request_is_cancelled() -> None:
    context = make_service()
    context.recommendation_service.get_candidates.side_effect = (
        asyncio.CancelledError
    )

    with pytest.raises(asyncio.CancelledError):
        await context.service.generate(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    updates = context.trip_repository.update.call_args_list
    context.trip_repository.claim_generation.assert_called_once()
    assert updates[-1].args[1]["status"] == "PLANNING"


@pytest.mark.anyio
async def test_generate_rejects_concurrent_generation_claim() -> None:
    original = make_trip(
        trip_status=TripStatus.PLANNING,
    )
    generating = make_trip(
        trip_status=TripStatus.GENERATING,
    )

    context = make_service(
        trip=original,
    )

    context.trip_repository.get_by_id.side_effect = [
        original,
        generating,
    ]

    context.trip_repository.claim_generation.side_effect = None
    context.trip_repository.claim_generation.return_value = None

    with pytest.raises(AppException) as captured:
        await context.service.generate(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.status_code == 409
    assert captured.value.code == (
        "TRIP_GENERATION_IN_PROGRESS"
    )

    context.plan_repository.commit_generated_plan.assert_not_called()
