from datetime import datetime, timezone

import pytest

import app.repositories.itinerary_plan_repository as repository_module
from app.repositories.itinerary_plan_repository import (
    ItineraryPlanRepository,
)
from app.schemas.itinerary_plan import (
    ItineraryPlanDocument,
    ItineraryPlanStatus,
)


NOW = datetime(
    2026,
    8,
    12,
    14,
    0,
    tzinfo=timezone.utc,
)


class FakeSnapshot:
    def __init__(
        self,
        document_id: str,
        data: dict | None,
    ) -> None:
        self.id = document_id
        self._data = data

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self) -> dict | None:
        if self._data is None:
            return None

        return dict(self._data)


class FakeDocumentReference:
    def __init__(
        self,
        collection: "FakeCollection",
        document_id: str,
    ) -> None:
        self._collection = collection
        self.id = document_id

    def get(self) -> FakeSnapshot:
        return FakeSnapshot(
            self.id,
            self._collection.documents.get(self.id),
        )

    def set(self, data: dict) -> None:
        self._collection.documents[self.id] = dict(data)

    def update(self, updates: dict) -> None:
        current = self._collection.documents.setdefault(
            self.id,
            {},
        )
        current.update(updates)

    def delete(self) -> None:
        self._collection.documents.pop(
            self.id,
            None,
        )


class FakeCollection:
    def __init__(self) -> None:
        self.documents: dict[str, dict] = {}
        self._counter = 0

    def document(
        self,
        document_id: str | None = None,
    ) -> FakeDocumentReference:
        if document_id is None:
            self._counter += 1
            document_id = f"plan_auto_{self._counter}"

        return FakeDocumentReference(
            self,
            document_id,
        )


class FakeTransaction:
    def set(
        self,
        reference: FakeDocumentReference,
        data: dict,
    ) -> None:
        reference.set(data)

    def update(
        self,
        reference: FakeDocumentReference,
        updates: dict,
    ) -> None:
        reference.update(updates)

    def delete(
        self,
        reference: FakeDocumentReference,
    ) -> None:
        reference.delete()


class FakeClient:
    def __init__(self) -> None:
        self.collections: dict[str, FakeCollection] = {}

    def collection(
        self,
        name: str,
    ) -> FakeCollection:
        if name not in self.collections:
            self.collections[name] = FakeCollection()

        return self.collections[name]

    def transaction(self) -> FakeTransaction:
        return FakeTransaction()


@pytest.fixture(autouse=True)
def bypass_firestore_transactional(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        repository_module,
        "transactional",
        lambda function: function,
    )


def make_plan() -> ItineraryPlanDocument:
    return ItineraryPlanDocument(
        trip_id="trip_001",
        user_id="firebase-user-123",
        status=ItineraryPlanStatus.ACTIVE,
        algorithm_version="greedy-anchor-v0.1",
        total_travel_minutes=24,
        days=[
            {
                "date": "2026-08-15",
                "dayType": "GAME_DAY",
                "items": [
                    {
                        "itemId": "item_1_1",
                        "type": "STADIUM",
                        "sequence": 1,
                        "placeId": "sajik",
                        "name": "사직야구장",
                        "address": "부산광역시 동래구 사직로 45",
                        "latitude": 35.194,
                        "longitude": 129.0615,
                        "scheduledStartAt": (
                            "2026-08-15T17:20:00+09:00"
                        ),
                        "scheduledEndAt": (
                            "2026-08-15T21:00:00+09:00"
                        ),
                        "travelMinutesFromPrevious": 24,
                        "travelTimeSource": "ODSAY",
                        "isRequired": True,
                    }
                ],
            }
        ],
        excluded_places=[],
        created_at=NOW,
        updated_at=NOW,
    )


def test_commit_generated_plan_saves_plan_and_updates_trip() -> None:
    client = FakeClient()

    client.collection("trips").documents["trip_001"] = {
        "status": "GENERATING",
        "activePlanId": None,
    }

    repository = ItineraryPlanRepository(client=client)

    result = repository.commit_generated_plan(
        trip_id="trip_001",
        plan=make_plan(),
        previous_plan_id=None,
    )

    assert result.plan_id == "plan_auto_1"
    assert result.status == ItineraryPlanStatus.ACTIVE

    stored_plan = client.collection(
        "itineraryPlans"
    ).documents["plan_auto_1"]

    assert stored_plan["tripId"] == "trip_001"
    assert stored_plan["userId"] == "firebase-user-123"
    assert stored_plan["status"] == "ACTIVE"
    assert stored_plan["days"][0]["items"][0]["itemId"] == (
        "item_1_1"
    )

    stored_trip = client.collection(
        "trips"
    ).documents["trip_001"]

    assert stored_trip["status"] == "GENERATED"
    assert stored_trip["activePlanId"] == "plan_auto_1"
    assert stored_trip["updatedAt"] == NOW


def test_commit_generated_plan_archives_previous_plan() -> None:
    client = FakeClient()

    client.collection("trips").documents["trip_001"] = {
        "status": "GENERATING",
        "activePlanId": "plan_old",
    }

    client.collection(
        "itineraryPlans"
    ).documents["plan_old"] = {
        "status": "ACTIVE",
        "updatedAt": NOW,
    }

    repository = ItineraryPlanRepository(client=client)

    result = repository.commit_generated_plan(
        trip_id="trip_001",
        plan=make_plan(),
        previous_plan_id="plan_old",
    )

    previous = client.collection(
        "itineraryPlans"
    ).documents["plan_old"]

    assert previous["status"] == "ARCHIVED"
    assert previous["updatedAt"] == NOW

    trip = client.collection(
        "trips"
    ).documents["trip_001"]

    assert trip["activePlanId"] == result.plan_id
    assert trip["status"] == "GENERATED"


def test_get_by_id_returns_plan_record() -> None:
    client = FakeClient()
    repository = ItineraryPlanRepository(client=client)

    plan = make_plan()

    client.collection(
        "itineraryPlans"
    ).documents["plan_001"] = plan.model_dump(
        by_alias=True,
        exclude_none=False,
    )

    result = repository.get_by_id("plan_001")

    assert result is not None
    assert result.plan_id == "plan_001"
    assert result.trip_id == "trip_001"
    assert result.algorithm_version == "greedy-anchor-v0.1"


def test_get_by_id_returns_none_when_missing() -> None:
    client = FakeClient()
    repository = ItineraryPlanRepository(client=client)

    assert repository.get_by_id("missing_plan") is None



def test_delete_active_plan_removes_plan_and_resets_trip() -> None:
    client = FakeClient()

    client.collection("trips").documents["trip_001"] = {
        "status": "GENERATED",
        "activePlanId": "plan_001",
        "updatedAt": NOW,
    }

    client.collection(
        "itineraryPlans"
    ).documents["plan_001"] = (
        make_plan().model_dump(
            by_alias=True,
            exclude_none=False,
        )
    )

    repository = ItineraryPlanRepository(
        client=client
    )

    repository.delete_active_plan(
        trip_id="trip_001",
        plan_id="plan_001",
        updated_at=NOW,
    )

    assert "plan_001" not in client.collection(
        "itineraryPlans"
    ).documents

    trip = client.collection(
        "trips"
    ).documents["trip_001"]

    assert trip["status"] == "PLANNING"
    assert trip["activePlanId"] is None
    assert trip["updatedAt"] == NOW


def test_update_schedule_updates_editable_fields() -> None:
    client = FakeClient()

    original = make_plan()

    client.collection(
        "itineraryPlans"
    ).documents["plan_001"] = (
        original.model_dump(
            by_alias=True,
            exclude_none=False,
        )
    )

    repository = ItineraryPlanRepository(
        client=client
    )

    result = repository.update_schedule(
        plan_id="plan_001",
        days=original.days,
        total_travel_minutes=123,
        updated_at=NOW,
    )

    assert result is not None
    assert result.plan_id == "plan_001"
    assert result.total_travel_minutes == 123
    assert result.updated_at == NOW

    stored = client.collection(
        "itineraryPlans"
    ).documents["plan_001"]

    assert stored["totalTravelMinutes"] == 123
    assert stored["updatedAt"] == NOW
    assert stored["days"] == [
        day.model_dump(
            by_alias=True,
            exclude_none=False,
        )
        for day in original.days
    ]
