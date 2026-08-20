from datetime import datetime, timezone
from typing import Any

from google.api_core.exceptions import AlreadyExists

from app.repositories.place_selection_repository import (
    PlaceSelectionRepository,
)
from app.schemas.place_selection import PlaceSelectionDocument


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

    def get(self) -> FakeDocumentSnapshot:
        return FakeDocumentSnapshot(
            self.id,
            self._documents.get(self.id),
        )

    def create(
        self,
        data: dict[str, Any],
    ) -> None:
        if self.id in self._documents:
            raise AlreadyExists(
                "document already exists"
            )

        self._documents[self.id] = dict(data)

    def delete(self) -> None:
        self._documents.pop(self.id, None)


class FakeCollectionReference:
    def __init__(
        self,
        documents: dict[str, dict[str, Any]],
    ) -> None:
        self._documents = documents

    def document(
        self,
        document_id: str,
    ) -> FakeDocumentReference:
        return FakeDocumentReference(
            self._documents,
            document_id,
        )

    def stream(self) -> list[FakeDocumentSnapshot]:
        return [
            FakeDocumentSnapshot(
                document_id,
                data,
            )
            for document_id, data
            in self._documents.items()
        ]


class FakeTripDocumentReference:
    def __init__(
        self,
        client: "FakeFirestoreClient",
        trip_id: str,
    ) -> None:
        self._client = client
        self._trip_id = trip_id

    def collection(
        self,
        collection_name: str,
    ) -> FakeCollectionReference:
        key = (
            self._trip_id,
            collection_name,
        )

        documents = self._client.subcollections.setdefault(
            key,
            {},
        )

        return FakeCollectionReference(documents)


class FakeTripsCollectionReference:
    def __init__(
        self,
        client: "FakeFirestoreClient",
    ) -> None:
        self._client = client

    def document(
        self,
        trip_id: str,
    ) -> FakeTripDocumentReference:
        return FakeTripDocumentReference(
            self._client,
            trip_id,
        )


class FakeFirestoreClient:
    def __init__(self) -> None:
        self.subcollections: dict[
            tuple[str, str],
            dict[str, dict[str, Any]],
        ] = {}

    def collection(
        self,
        collection_name: str,
    ) -> FakeTripsCollectionReference:
        assert collection_name == "trips"

        return FakeTripsCollectionReference(self)


def make_selection(
    *,
    place_id: str = "tour_123456",
    is_required: bool = True,
    created_at: datetime | None = None,
) -> PlaceSelectionDocument:
    return PlaceSelectionDocument(
        place_id=place_id,
        is_required=is_required,
        created_at=(
            created_at
            or datetime(
                2026,
                8,
                12,
                10,
                0,
                tzinfo=timezone.utc,
            )
        ),
    )


def test_create_stores_place_id_as_document_id() -> None:
    client = FakeFirestoreClient()
    repository = PlaceSelectionRepository(
        client=client
    )

    created = repository.create(
        trip_id="trip_001",
        selection=make_selection(),
    )

    assert created is not None
    assert created.place_id == "tour_123456"
    assert created.is_required is True

    stored = client.subcollections[
        ("trip_001", "placeSelections")
    ]["tour_123456"]

    assert stored["placeId"] == "tour_123456"
    assert stored["isRequired"] is True
    assert isinstance(
        stored["createdAt"],
        datetime,
    )


def test_create_duplicate_returns_none() -> None:
    client = FakeFirestoreClient()
    repository = PlaceSelectionRepository(
        client=client
    )

    selection = make_selection()

    first = repository.create(
        trip_id="trip_001",
        selection=selection,
    )
    second = repository.create(
        trip_id="trip_001",
        selection=selection,
    )

    assert first is not None
    assert second is None

    stored = client.subcollections[
        ("trip_001", "placeSelections")
    ]

    assert len(stored) == 1


def test_get_all_returns_oldest_first() -> None:
    client = FakeFirestoreClient()
    repository = PlaceSelectionRepository(
        client=client
    )

    repository.create(
        trip_id="trip_001",
        selection=make_selection(
            place_id="tour_002",
            created_at=datetime(
                2026,
                8,
                12,
                11,
                0,
                tzinfo=timezone.utc,
            ),
        ),
    )

    repository.create(
        trip_id="trip_001",
        selection=make_selection(
            place_id="tour_001",
            created_at=datetime(
                2026,
                8,
                12,
                10,
                0,
                tzinfo=timezone.utc,
            ),
        ),
    )

    selections = repository.get_all(
        trip_id="trip_001"
    )

    assert [
        selection.place_id
        for selection in selections
    ] == [
        "tour_001",
        "tour_002",
    ]


def test_delete_returns_true_and_removes_selection() -> None:
    client = FakeFirestoreClient()
    repository = PlaceSelectionRepository(
        client=client
    )

    repository.create(
        trip_id="trip_001",
        selection=make_selection(),
    )

    deleted = repository.delete(
        trip_id="trip_001",
        place_id="tour_123456",
    )

    assert deleted is True
    assert repository.get_all(
        trip_id="trip_001"
    ) == []


def test_delete_missing_selection_returns_false() -> None:
    client = FakeFirestoreClient()
    repository = PlaceSelectionRepository(
        client=client
    )

    deleted = repository.delete(
        trip_id="trip_001",
        place_id="tour_missing",
    )

    assert deleted is False


def test_delete_all_removes_all_trip_selections() -> None:
    client = FakeFirestoreClient()
    repository = PlaceSelectionRepository(
        client=client
    )

    repository.create(
        trip_id="trip_001",
        selection=make_selection(
            place_id="tour_001",
        ),
    )
    repository.create(
        trip_id="trip_001",
        selection=make_selection(
            place_id="tour_002",
        ),
    )
    repository.create(
        trip_id="trip_002",
        selection=make_selection(
            place_id="tour_other",
        ),
    )

    deleted_count = repository.delete_all(
        trip_id="trip_001",
    )

    assert deleted_count == 2
    assert repository.get_all(
        trip_id="trip_001"
    ) == []
    assert len(
        repository.get_all(
            trip_id="trip_002"
        )
    ) == 1
