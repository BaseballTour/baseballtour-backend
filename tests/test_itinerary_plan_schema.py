import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.itinerary import ItineraryResult
from app.schemas.itinerary_plan import (
    ItineraryPlanAddItemRequest,
    ItineraryPlanDocument,
    ItineraryPlanReorderRequest,
    ItineraryPlanStatus,
)


RESULT_SAMPLE_PATH = (
    Path(__file__).resolve().parents[1]
    / "samples"
    / "algorithm"
    / "itinerary_result.json"
)


def create_plan_document() -> ItineraryPlanDocument:
    result = ItineraryResult.model_validate_json(
        RESULT_SAMPLE_PATH.read_text(encoding="utf-8")
    )

    stored_days = [
        {
            **day.model_dump(by_alias=True),
            "items": [
                {
                    **item.model_dump(by_alias=True),
                    "itemId": f"item_{day_index}_{item_index}",
                }
                for item_index, item in enumerate(
                    day.items,
                    start=1,
                )
            ],
        }
        for day_index, day in enumerate(result.days, start=1)
    ]

    return ItineraryPlanDocument(
        trip_id=result.trip_id,
        user_id="firebase-user-123",
        algorithm_version=result.algorithm_version,
        total_travel_minutes=result.total_travel_minutes,
        days=stored_days,
        excluded_places=result.excluded_places,
        created_at=datetime.fromisoformat(
            "2026-08-05T09:00:00+09:00"
        ),
        updated_at=datetime.fromisoformat(
            "2026-08-05T09:00:00+09:00"
        ),
    )


def test_plan_document_defaults_to_active() -> None:
    document = create_plan_document()

    assert document.status == ItineraryPlanStatus.ACTIVE
    assert document.trip_id == "trip_001"


def test_plan_document_serializes_storage_metadata() -> None:
    document = create_plan_document()
    data = json.loads(document.model_dump_json(by_alias=True))

    assert data["status"] == "ACTIVE"
    assert data["tripId"] == "trip_001"
    assert data["userId"] == "firebase-user-123"
    assert data["days"][0]["items"][0]["itemId"] == (
        "item_1_1"
    )
    assert data["days"][0]["items"][0]["isFixed"] is False
    assert "planId" not in data


def test_plan_document_serializes_item_times_in_korea_timezone() -> None:
    document = create_plan_document()
    item = document.days[0].items[0]
    item.scheduled_start_at = datetime.fromisoformat(
        "2026-08-16T07:20:00+00:00"
    )
    item.scheduled_end_at = datetime.fromisoformat(
        "2026-08-16T11:00:00+00:00"
    )

    data = document.model_dump(mode="json", by_alias=True)
    serialized_item = data["days"][0]["items"][0]

    assert serialized_item["scheduledStartAt"] == (
        "2026-08-16T16:20:00+09:00"
    )
    assert serialized_item["scheduledEndAt"] == (
        "2026-08-16T20:00:00+09:00"
    )


def test_algorithm_result_has_no_storage_status() -> None:
    result = ItineraryResult.model_validate_json(
        RESULT_SAMPLE_PATH.read_text(encoding="utf-8")
    )

    assert "status" not in result.model_dump()
    assert "userId" not in result.model_dump()


def test_plan_document_rejects_generation_status() -> None:
    data = create_plan_document().model_dump()
    data["status"] = "FAILED"

    with pytest.raises(ValidationError):
        ItineraryPlanDocument.model_validate(data)


def test_reorder_request_uses_camel_case() -> None:
    request = ItineraryPlanReorderRequest(
        date="2026-08-15",
        item_ids=[
            "item_1_2",
            "item_1_1",
        ],
    )

    dumped = request.model_dump(
        by_alias=True
    )

    assert dumped["date"].isoformat() == "2026-08-15"
    assert dumped["itemIds"] == [
        "item_1_2",
        "item_1_1",
    ]


def test_reorder_request_rejects_duplicate_item_ids() -> None:
    with pytest.raises(ValidationError):
        ItineraryPlanReorderRequest(
            date="2026-08-15",
            item_ids=[
                "item_1_1",
                "item_1_1",
            ],
        )


def test_reorder_request_rejects_empty_item_id() -> None:
    with pytest.raises(ValidationError):
        ItineraryPlanReorderRequest(
            date="2026-08-15",
            item_ids=[
                "item_1_1",
                "",
            ],
        )


def test_add_item_request_uses_camel_case() -> None:
    request = ItineraryPlanAddItemRequest(
        date="2026-08-15",
        place_id="tour_123456",
        is_required=True,
    )

    dumped = request.model_dump(
        by_alias=True
    )

    assert dumped["date"].isoformat() == "2026-08-15"
    assert dumped["placeId"] == "tour_123456"
    assert dumped["isRequired"] is True


def test_add_item_request_defaults_to_required() -> None:
    request = ItineraryPlanAddItemRequest(
        place_id="tour_123456",
    )

    assert request.is_required is True
    assert request.date is None
    assert request.scheduled_start_at is None
