import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.itinerary import ItineraryResult
from app.schemas.itinerary_plan import (
    ItineraryPlanDocument,
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
    assert "planId" not in data


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
