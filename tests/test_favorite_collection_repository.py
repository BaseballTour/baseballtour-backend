from datetime import datetime, timezone
from typing import Any

from google.api_core.exceptions import AlreadyExists
from google.cloud.exceptions import NotFound

from app.repositories.favorite_collection_repository import (
    FavoriteCollectionRepository,
)
from app.schemas.favorite_collection import (
    FavoriteCollectionDocument,
    FavoriteCollectionItemDocument,
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
        *,
        client: "FakeFirestoreClient",
        documents: dict[str, dict[str, Any]],
        document_id: str,
        user_id: str,
        collection_name: str,
    ) -> None:
        self._client = client
        self._documents = documents
        self.id = document_id
        self._user_id = user_id
        self._collection_name = collection_name

    def get(self) -> FakeDocumentSnapshot:
        return FakeDocumentSnapshot(
            self.id,
            self._documents.get(self.id),
        )

    def set(
        self,
        data: dict[str, Any],
    ) -> None:
        self._documents[self.id] = dict(data)

    def create(
        self,
        data: dict[str, Any],
    ) -> None:
        if self.id in self._documents:
            raise AlreadyExists(
                "document already exists"
            )

        self._documents[self.id] = dict(data)

    def update(
        self,
        data: dict[str, Any],
    ) -> None:
        if self.id not in self._documents:
            raise NotFound("document does not exist")

        self._documents[self.id].update(data)

    def delete(self) -> None:
        self._documents.pop(self.id, None)

    def collection(
        self,
        collection_name: str,
    ) -> "FakeCollectionReference":
        key = (
            self._user_id,
            self.id,
            collection_name,
        )

        documents = self._client.item_subcollections.setdefault(
            key,
            {},
        )

        return FakeCollectionReference(
            client=self._client,
            documents=documents,
            user_id=self._user_id,
            collection_name=collection_name,
        )


class FakeCollectionReference:
    def __init__(
        self,
        *,
        client: "FakeFirestoreClient",
        documents: dict[str, dict[str, Any]],
        user_id: str,
        collection_name: str,
    ) -> None:
        self._client = client
        self._documents = documents
        self._user_id = user_id
        self._collection_name = collection_name

    def document(
        self,
        document_id: str | None = None,
    ) -> FakeDocumentReference:
        if document_id is None:
            self._client.next_id += 1
            document_id = (
                f"collection_{self._client.next_id:03d}"
            )

        return FakeDocumentReference(
            client=self._client,
            documents=self._documents,
            document_id=document_id,
            user_id=self._user_id,
            collection_name=self._collection_name,
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


class FakeUserDocumentReference:
    def __init__(
        self,
        client: "FakeFirestoreClient",
        user_id: str,
    ) -> None:
        self._client = client
        self._user_id = user_id

    def collection(
        self,
        collection_name: str,
    ) -> FakeCollectionReference:
        key = (
            self._user_id,
            collection_name,
        )

        documents = self._client.subcollections.setdefault(
            key,
            {},
        )

        return FakeCollectionReference(
            client=self._client,
            documents=documents,
            user_id=self._user_id,
            collection_name=collection_name,
        )


class FakeUsersCollectionReference:
    def __init__(
        self,
        client: "FakeFirestoreClient",
    ) -> None:
        self._client = client

    def document(
        self,
        user_id: str,
    ) -> FakeUserDocumentReference:
        return FakeUserDocumentReference(
            self._client,
            user_id,
        )


class FakeFirestoreClient:
    def __init__(self) -> None:
        self.next_id = 0
        self.subcollections: dict[
            tuple[str, str],
            dict[str, dict[str, Any]],
        ] = {}
        self.item_subcollections: dict[
            tuple[str, str, str],
            dict[str, dict[str, Any]],
        ] = {}

    def collection(
        self,
        collection_name: str,
    ) -> FakeUsersCollectionReference:
        assert collection_name == "users"

        return FakeUsersCollectionReference(self)


def make_collection(
    *,
    name: str = "가보고 싶은 장소",
    created_at: datetime | None = None,
) -> FavoriteCollectionDocument:
    now = (
        created_at
        or datetime(
            2026,
            8,
            20,
            9,
            0,
            tzinfo=timezone.utc,
        )
    )

    return FavoriteCollectionDocument(
        name=name,
        created_at=now,
        updated_at=now,
    )


def test_create_stores_collection_under_user() -> None:
    client = FakeFirestoreClient()
    repository = FavoriteCollectionRepository(
        client=client
    )

    created = repository.create(
        user_id="user_001",
        collection=make_collection(),
    )

    assert created.collection_id.startswith("collection_")
    assert created.name == "가보고 싶은 장소"

    stored = client.subcollections[
        ("user_001", "favoriteCollections")
    ][created.collection_id]

    assert stored["name"] == "가보고 싶은 장소"
    assert isinstance(stored["createdAt"], datetime)
    assert isinstance(stored["updatedAt"], datetime)


def test_get_all_returns_oldest_first() -> None:
    client = FakeFirestoreClient()
    repository = FavoriteCollectionRepository(
        client=client
    )

    repository.create(
        user_id="user_001",
        collection=make_collection(
            name="두 번째",
            created_at=datetime(
                2026,
                8,
                20,
                11,
                0,
                tzinfo=timezone.utc,
            ),
        ),
    )

    repository.create(
        user_id="user_001",
        collection=make_collection(
            name="첫 번째",
            created_at=datetime(
                2026,
                8,
                20,
                10,
                0,
                tzinfo=timezone.utc,
            ),
        ),
    )

    collections = repository.get_all(
        user_id="user_001"
    )

    assert [
        collection.name
        for collection in collections
    ] == [
        "첫 번째",
        "두 번째",
    ]


def test_get_by_id_returns_collection() -> None:
    client = FakeFirestoreClient()
    repository = FavoriteCollectionRepository(
        client=client
    )

    created = repository.create(
        user_id="user_001",
        collection=make_collection(),
    )

    found = repository.get_by_id(
        user_id="user_001",
        collection_id=created.collection_id,
    )

    assert found is not None
    assert found.collection_id == created.collection_id
    assert found.name == "가보고 싶은 장소"


def test_update_name_updates_collection() -> None:
    client = FakeFirestoreClient()
    repository = FavoriteCollectionRepository(
        client=client
    )

    created = repository.create(
        user_id="user_001",
        collection=make_collection(),
    )

    updated_at = datetime(
        2026,
        8,
        20,
        12,
        0,
        tzinfo=timezone.utc,
    )

    updated = repository.update_name(
        user_id="user_001",
        collection_id=created.collection_id,
        name="부산 원정",
        updated_at=updated_at,
    )

    assert updated is True

    stored = client.subcollections[
        ("user_001", "favoriteCollections")
    ][created.collection_id]

    assert stored["name"] == "부산 원정"
    assert stored["updatedAt"] == updated_at


def test_update_missing_collection_returns_false() -> None:
    client = FakeFirestoreClient()
    repository = FavoriteCollectionRepository(
        client=client
    )

    updated = repository.update_name(
        user_id="user_001",
        collection_id="missing",
        name="새 이름",
        updated_at=datetime.now(timezone.utc),
    )

    assert updated is False


def test_delete_removes_items_before_collection() -> None:
    client = FakeFirestoreClient()
    repository = FavoriteCollectionRepository(
        client=client
    )

    created = repository.create(
        user_id="user_001",
        collection=make_collection(),
    )

    client.item_subcollections[
        (
            "user_001",
            created.collection_id,
            "items",
        )
    ] = {
        "tour_001": {
            "placeId": "tour_001",
        },
        "tour_002": {
            "placeId": "tour_002",
        },
    }

    repository.delete(
        user_id="user_001",
        collection_id=created.collection_id,
    )

    assert created.collection_id not in (
        client.subcollections[
            ("user_001", "favoriteCollections")
        ]
    )

    assert (
        client.item_subcollections[
            (
                "user_001",
                created.collection_id,
                "items",
            )
        ]
        == {}
    )


def test_save_item_stores_place_id_as_document_id() -> None:
    client = FakeFirestoreClient()
    repository = FavoriteCollectionRepository(
        client=client
    )

    collection = repository.create(
        user_id="user_001",
        collection=make_collection(),
    )

    created_at = datetime(
        2026,
        8,
        20,
        13,
        0,
        tzinfo=timezone.utc,
    )

    item = FavoriteCollectionItemDocument(
        place_id="tour_123456",
        created_at=created_at,
    )

    saved = repository.save_item(
        user_id="user_001",
        collection_id=collection.collection_id,
        item=item,
    )

    assert saved.place_id == "tour_123456"
    assert saved.created_at == created_at

    stored = client.item_subcollections[
        (
            "user_001",
            collection.collection_id,
            "items",
        )
    ]["tour_123456"]

    assert stored == {
        "placeId": "tour_123456",
        "createdAt": created_at,
    }


def test_save_item_duplicate_returns_existing_item() -> None:
    client = FakeFirestoreClient()
    repository = FavoriteCollectionRepository(
        client=client
    )

    collection = repository.create(
        user_id="user_001",
        collection=make_collection(),
    )

    first_time = datetime(
        2026,
        8,
        20,
        13,
        0,
        tzinfo=timezone.utc,
    )

    first = repository.save_item(
        user_id="user_001",
        collection_id=collection.collection_id,
        item=FavoriteCollectionItemDocument(
            place_id="tour_123456",
            created_at=first_time,
        ),
    )

    second = repository.save_item(
        user_id="user_001",
        collection_id=collection.collection_id,
        item=FavoriteCollectionItemDocument(
            place_id="tour_123456",
            created_at=datetime(
                2026,
                8,
                20,
                14,
                0,
                tzinfo=timezone.utc,
            ),
        ),
    )

    assert first.created_at == first_time
    assert second.created_at == first_time

    stored = client.item_subcollections[
        (
            "user_001",
            collection.collection_id,
            "items",
        )
    ]

    assert len(stored) == 1


def test_get_items_returns_oldest_first() -> None:
    client = FakeFirestoreClient()
    repository = FavoriteCollectionRepository(
        client=client
    )

    collection = repository.create(
        user_id="user_001",
        collection=make_collection(),
    )

    repository.save_item(
        user_id="user_001",
        collection_id=collection.collection_id,
        item=FavoriteCollectionItemDocument(
            place_id="tour_002",
            created_at=datetime(
                2026,
                8,
                20,
                14,
                0,
                tzinfo=timezone.utc,
            ),
        ),
    )

    repository.save_item(
        user_id="user_001",
        collection_id=collection.collection_id,
        item=FavoriteCollectionItemDocument(
            place_id="tour_001",
            created_at=datetime(
                2026,
                8,
                20,
                13,
                0,
                tzinfo=timezone.utc,
            ),
        ),
    )

    items = repository.get_items(
        user_id="user_001",
        collection_id=collection.collection_id,
    )

    assert [
        item.place_id
        for item in items
    ] == [
        "tour_001",
        "tour_002",
    ]


def test_delete_item_returns_true_and_removes_item() -> None:
    client = FakeFirestoreClient()
    repository = FavoriteCollectionRepository(
        client=client
    )

    collection = repository.create(
        user_id="user_001",
        collection=make_collection(),
    )

    repository.save_item(
        user_id="user_001",
        collection_id=collection.collection_id,
        item=FavoriteCollectionItemDocument(
            place_id="tour_123456",
            created_at=datetime.now(timezone.utc),
        ),
    )

    deleted = repository.delete_item(
        user_id="user_001",
        collection_id=collection.collection_id,
        place_id="tour_123456",
    )

    assert deleted is True
    assert repository.get_items(
        user_id="user_001",
        collection_id=collection.collection_id,
    ) == []


def test_delete_missing_item_returns_false() -> None:
    client = FakeFirestoreClient()
    repository = FavoriteCollectionRepository(
        client=client
    )

    collection = repository.create(
        user_id="user_001",
        collection=make_collection(),
    )

    deleted = repository.delete_item(
        user_id="user_001",
        collection_id=collection.collection_id,
        place_id="tour_missing",
    )

    assert deleted is False


def test_delete_all_by_user_id_removes_collections_and_items() -> None:
    client = FakeFirestoreClient()
    repository = FavoriteCollectionRepository(
        client=client
    )

    first = repository.create(
        user_id="user_001",
        collection=make_collection(
            name="맛집",
        ),
    )
    second = repository.create(
        user_id="user_001",
        collection=make_collection(
            name="관광지",
        ),
    )

    repository.save_item(
        user_id="user_001",
        collection_id=first.collection_id,
        item=FavoriteCollectionItemDocument(
            place_id="tour_001",
            created_at=datetime.now(timezone.utc),
        ),
    )
    repository.save_item(
        user_id="user_001",
        collection_id=second.collection_id,
        item=FavoriteCollectionItemDocument(
            place_id="tour_002",
            created_at=datetime.now(timezone.utc),
        ),
    )

    deleted_count = repository.delete_all_by_user_id(
        user_id="user_001",
    )

    assert deleted_count == 2

    assert repository.get_all(
        user_id="user_001"
    ) == []

    assert (
        client.item_subcollections[
            (
                "user_001",
                first.collection_id,
                "items",
            )
        ]
        == {}
    )

    assert (
        client.item_subcollections[
            (
                "user_001",
                second.collection_id,
                "items",
            )
        ]
        == {}
    )
