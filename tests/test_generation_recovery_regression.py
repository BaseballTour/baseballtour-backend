import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from app.schemas.trip import TripRecord, TripStatus
from app.services.itinerary_generation_service import (
    GENERATION_STALE_AFTER,
    ItineraryGenerationService,
)


NOW = datetime(2026, 8, 15, 3, 0, tzinfo=timezone.utc)


def make_trip(*, status, active_plan_id=None):
    return TripRecord.model_construct(
        trip_id="trip_001",
        user_id="owner_001",
        game_id="game_001",
        title="부산 원정",
        trip_start_at=NOW,
        trip_end_at=NOW + timedelta(days=1),
        status=status,
        active_plan_id=active_plan_id,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.parametrize(
    "original_status,active_plan_id",
    [
        (TripStatus.PLANNING, None),
        (TripStatus.GENERATED, "plan_001"),
    ],
)
def test_generation_failure_requests_original_status_restore(
    monkeypatch,
    original_status,
    active_plan_id,
):
    trip = make_trip(
        status=original_status,
        active_plan_id=active_plan_id,
    )
    repository = Mock()
    repository.claim_generation.side_effect = lambda **kwargs: (
        trip.model_copy(
            update={
                "status": TripStatus.GENERATING,
                "updated_at": kwargs["updated_at"],
            }
        )
    )

    service = object.__new__(ItineraryGenerationService)
    service._trip_repository = repository

    monkeypatch.setattr(
        service,
        "_get_owned_trip_or_raise",
        lambda **kwargs: trip,
    )
    monkeypatch.setattr(
        service,
        "_validate_required_points",
        lambda trip: None,
    )
    monkeypatch.setattr(
        service,
        "_get_game_or_raise",
        Mock(side_effect=RuntimeError("generation failed")),
    )

    restore = Mock()
    monkeypatch.setattr(service, "_restore_trip_status", restore)

    with pytest.raises(RuntimeError, match="generation failed"):
        asyncio.run(service.generate(
            user_id="owner_001",
            trip_id="trip_001",
        ))

    restore.assert_called_once_with(
        trip_id="trip_001",
        original_status=original_status,
    )
    repository.claim_generation.assert_called_once()


def test_stale_generation_uses_configured_recovery_window():
    trip = make_trip(
        status=TripStatus.GENERATING,
        active_plan_id="plan_001",
    )
    recovered = trip.model_copy(
        update={"status": TripStatus.GENERATED}
    )

    repository = Mock()
    repository.recover_stale_generation.return_value = recovered

    service = object.__new__(ItineraryGenerationService)
    service._trip_repository = repository

    result = service._recover_stale_generation(trip)

    assert result.status == TripStatus.GENERATED
    assert result.active_plan_id == "plan_001"

    kwargs = repository.recover_stale_generation.call_args.kwargs
    assert kwargs["trip_id"] == "trip_001"
    assert (
        kwargs["updated_at"] - kwargs["stale_before"]
        == GENERATION_STALE_AFTER
    )
