from datetime import datetime, timezone
from typing import Any

import pytest
from google.cloud.exceptions import NotFound

import app.repositories.trip_repository as trip_repository_module
from app.repositories.trip_repository import (
    TripIdempotencyConflictError,
    TripRepository,
)
from app.schemas.trip import (
    AccommodationInfo,
    TripDocument,
    TripPoint,
    TripStatus,
)


class FakeDocumentSnapshot:
    def __init__(
        self,
        document_id: str,
        data: dict[str, Any] | None,
    ) -> None:
        self.id = document_id
        self._data = data
        self.exists = data is not None

    def to_dict(self) -> dict[str, Any] | None:
        if self._data is None:
            return None

        return dict(self._data)


class FakeDocumentReference:
    def __init__(
        self,
        documents: dict[str, dict[str, Any]],
        document_id: str,
    ) -> None:
        self._documents = documents
        self.id = document_id

    def get(
        self,
        transaction=None,
    ) -> FakeDocumentSnapshot:
        return FakeDocumentSnapshot(
            self.id,
            self._documents.get(self.id),
        )

    def set(self, data: dict[str, Any]) -> None:
        self._documents[self.id] = dict(data)

    def update(self, updates: dict[str, Any]) -> None:
        if self.id not in self._documents:
            raise NotFound("document not found")

        self._documents[self.id].update(updates)

    def delete(self) -> None:
        self._documents.pop(self.id, None)


class FakeQuery:
    def __init__(
        self,
        documents: dict[str, dict[str, Any]],
        field_path: str,
        expected_value: Any,
    ) -> None:
        self._documents = documents
        self._field_path = field_path
        self._expected_value = expected_value
        self._order_field: str | None = None
        self._order_direction = "ASCENDING"

    def order_by(
        self,
        field_path: str,
        direction: str = "ASCENDING",
    ) -> "FakeQuery":
        self._order_field = field_path
        self._order_direction = direction
        return self

    def stream(self) -> list[FakeDocumentSnapshot]:
        documents = [
            (
                document_id,
                data,
            )
            for document_id, data in self._documents.items()
            if data.get(self._field_path)
            == self._expected_value
        ]

        if self._order_field is not None:
            documents.sort(
                key=lambda item: item[1][
                    self._order_field
                ],
                reverse=(
                    self._order_direction
                    == "DESCENDING"
                ),
            )

        return [
            FakeDocumentSnapshot(
                document_id,
                data,
            )
            for document_id, data in documents
        ]


class FakeCollectionReference:
    def __init__(
        self,
        documents: dict[str, dict[str, Any]],
    ) -> None:
        self._documents = documents
        self._next_id = 1

    def document(
        self,
        document_id: str | None = None,
    ) -> FakeDocumentReference:
        if document_id is None:
            document_id = f"trip_auto_{self._next_id:03d}"
            self._next_id += 1

        return FakeDocumentReference(
            self._documents,
            document_id,
        )

    def where(
        self,
        *,
        filter: Any,
    ) -> FakeQuery:
        return FakeQuery(
            self._documents,
            field_path=filter.field_path,
            expected_value=filter.value,
        )


class FakeTransaction:
    def set(
        self,
        document_reference: FakeDocumentReference,
        data: dict[str, Any],
    ) -> None:
        document_reference.set(data)

    def update(
        self,
        document_reference: FakeDocumentReference,
        updates: dict[str, Any],
    ) -> None:
        document_reference.update(updates)


class FakeFirestoreClient:
    def __init__(self) -> None:
        self.collections: dict[
            str,
            dict[str, dict[str, Any]],
        ] = {}
        self.collection_references: dict[
            str,
            FakeCollectionReference,
        ] = {}

    def transaction(self) -> FakeTransaction:
        return FakeTransaction()

    def collection(
        self,
        collection_name: str,
    ) -> FakeCollectionReference:
        documents = self.collections.setdefault(
            collection_name,
            {},
        )

        return self.collection_references.setdefault(
            collection_name,
            FakeCollectionReference(documents),
        )


def create_trip_document(
    *,
    user_id: str = "user-001",
    title: str = "두산 부산 원정",
    created_at: datetime | None = None,
) -> TripDocument:
    now = created_at or datetime.now(timezone.utc)

    return TripDocument(
        user_id=user_id,
        game_id="dev_game_20260815_lotte_doosan",
        title=title,
        trip_start_at=datetime(
            2026,
            8,
            14,
            1,
            30,
            tzinfo=timezone.utc,
        ),
        trip_end_at=datetime(
            2026,
            8,
            16,
            10,
            0,
            tzinfo=timezone.utc,
        ),
        arrival_point=TripPoint(
            name="부산역",
            latitude=35.1151,
            longitude=129.0414,
        ),
        departure_point=TripPoint(
            name="부산역",
            latitude=35.1151,
            longitude=129.0414,
        ),
        accommodation=AccommodationInfo(
            name="서면 숙소",
            address="부산광역시 부산진구",
            latitude=35.1577,
            longitude=129.0592,
            check_in_at=datetime(
                2026,
                8,
                14,
                6,
                0,
                tzinfo=timezone.utc,
            ),
            check_out_at=datetime(
                2026,
                8,
                16,
                2,
                0,
                tzinfo=timezone.utc,
            ),
        ),
        status="PLANNING",
        active_plan_id=None,
        created_at=now,
        updated_at=now,
    )


def test_create_uses_auto_id_and_returns_record() -> None:
    client = FakeFirestoreClient()
    repository = TripRepository(client=client)

    trip = repository.create(
        create_trip_document()
    )

    assert trip.trip_id == "trip_auto_001"
    assert trip.user_id == "user-001"
    assert trip.status.value == "PLANNING"
    assert repository.get_by_id(trip.trip_id) is not None


def test_create_stores_camel_case_and_datetime() -> None:
    client = FakeFirestoreClient()
    repository = TripRepository(client=client)

    trip = repository.create(
        create_trip_document()
    )

    stored = client.collections["trips"][
        trip.trip_id
    ]

    assert "userId" in stored
    assert "gameId" in stored
    assert "tripStartAt" in stored
    assert "tripEndAt" in stored
    assert "arrivalPoint" in stored
    assert "departurePoint" in stored
    assert "activePlanId" in stored
    assert "createdAt" in stored
    assert "updatedAt" in stored

    assert "user_id" not in stored
    assert "trip_start_at" not in stored

    assert isinstance(stored["tripStartAt"], datetime)
    assert isinstance(
        stored["accommodation"]["checkInAt"],
        datetime,
    )


def test_get_missing_trip_returns_none() -> None:
    client = FakeFirestoreClient()
    repository = TripRepository(client=client)

    assert repository.get_by_id("missing") is None


def test_get_by_user_id_filters_and_sorts_newest_first() -> None:
    client = FakeFirestoreClient()
    repository = TripRepository(client=client)

    repository.create(
        create_trip_document(
            user_id="user-001",
            title="이전 여행",
            created_at=datetime(
                2026,
                8,
                1,
                tzinfo=timezone.utc,
            ),
        )
    )
    repository.create(
        create_trip_document(
            user_id="user-002",
            title="다른 사용자 여행",
            created_at=datetime(
                2026,
                8,
                3,
                tzinfo=timezone.utc,
            ),
        )
    )
    repository.create(
        create_trip_document(
            user_id="user-001",
            title="최근 여행",
            created_at=datetime(
                2026,
                8,
                2,
                tzinfo=timezone.utc,
            ),
        )
    )

    trips = repository.get_by_user_id("user-001")

    assert [
        trip.title
        for trip in trips
    ] == [
        "최근 여행",
        "이전 여행",
    ]


def test_update_changes_only_provided_fields() -> None:
    client = FakeFirestoreClient()
    repository = TripRepository(client=client)

    trip = repository.create(
        create_trip_document()
    )
    updated_at = datetime(
        2026,
        8,
        4,
        tzinfo=timezone.utc,
    )

    updated_trip = repository.update(
        trip.trip_id,
        {
            "title": "수정된 부산 원정",
            "accommodation": None,
            "updatedAt": updated_at,
        },
    )

    assert updated_trip is not None
    assert updated_trip.title == "수정된 부산 원정"
    assert updated_trip.accommodation is None
    assert updated_trip.game_id == trip.game_id
    assert updated_trip.updated_at == updated_at


def test_update_missing_trip_returns_none() -> None:
    client = FakeFirestoreClient()
    repository = TripRepository(client=client)

    result = repository.update(
        "missing",
        {
            "title": "수정",
        },
    )

    assert result is None


def test_delete_removes_trip_and_is_safe_when_missing() -> None:
    client = FakeFirestoreClient()
    repository = TripRepository(client=client)

    trip = repository.create(
        create_trip_document()
    )

    repository.delete(trip.trip_id)

    assert repository.get_by_id(trip.trip_id) is None

    repository.delete(trip.trip_id)

    assert repository.get_by_id(trip.trip_id) is None


def test_claim_generation_only_updates_expected_status(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        trip_repository_module,
        "transactional",
        lambda function: function,
    )

    client = FakeFirestoreClient()
    repository = TripRepository(client=client)

    trip = repository.create(
        create_trip_document()
    )

    updated_at = datetime(
        2026,
        8,
        20,
        3,
        0,
        tzinfo=timezone.utc,
    )

    claimed = repository.claim_generation(
        trip_id=trip.trip_id,
        expected_status=TripStatus.PLANNING,
        updated_at=updated_at,
    )

    assert claimed is not None
    assert claimed.status == TripStatus.GENERATING
    assert claimed.updated_at == updated_at

    stored = repository.get_by_id(trip.trip_id)

    assert stored is not None
    assert stored.status == TripStatus.GENERATING

    duplicate_claim = repository.claim_generation(
        trip_id=trip.trip_id,
        expected_status=TripStatus.PLANNING,
        updated_at=updated_at,
    )

    assert duplicate_claim is None


def test_create_idempotent_reuses_same_trip(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        trip_repository_module,
        "transactional",
        lambda function: function,
    )

    client = FakeFirestoreClient()
    repository = TripRepository(client=client)

    trip = create_trip_document().model_copy(
        update={
            "idempotency_request_hash": "request-hash-1",
        }
    )

    first = repository.create_idempotent(
        trip=trip,
        idempotency_key="request-key-1",
    )
    second = repository.create_idempotent(
        trip=trip,
        idempotency_key="request-key-1",
    )

    assert first.trip_id == second.trip_id
    assert len(client.collections["trips"]) == 1


def test_create_idempotent_rejects_key_reuse_with_other_request(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        trip_repository_module,
        "transactional",
        lambda function: function,
    )

    client = FakeFirestoreClient()
    repository = TripRepository(client=client)

    first_trip = create_trip_document().model_copy(
        update={
            "idempotency_request_hash": "request-hash-1",
        }
    )
    other_trip = create_trip_document(
        title="다른 여행",
    ).model_copy(
        update={
            "idempotency_request_hash": "request-hash-2",
        }
    )

    repository.create_idempotent(
        trip=first_trip,
        idempotency_key="request-key-1",
    )

    with pytest.raises(TripIdempotencyConflictError):
        repository.create_idempotent(
            trip=other_trip,
            idempotency_key="request-key-1",
        )

    assert len(client.collections["trips"]) == 1
