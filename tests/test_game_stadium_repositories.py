from datetime import datetime, timezone
from typing import Any

from google.cloud.exceptions import Conflict

from app.repositories.game_repository import GameRepository
from app.repositories.stadium_repository import StadiumRepository
from app.schemas.game import GameDocument
from app.schemas.stadium import StadiumDocument


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
        self._document_id = document_id

    def get(self) -> FakeDocumentSnapshot:
        return FakeDocumentSnapshot(
            self._document_id,
            self._documents.get(self._document_id),
        )

    def set(self, data: dict[str, Any]) -> None:
        self._documents[self._document_id] = dict(data)

    def create(self, data: dict[str, Any]) -> None:
        if self._document_id in self._documents:
            raise Conflict("Document already exists.")

        self._documents[self._document_id] = dict(data)


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
            for document_id, data in self._documents.items()
        ]


class FakeFirestoreClient:
    def __init__(self) -> None:
        self.collections: dict[
            str,
            dict[str, dict[str, Any]],
        ] = {}

    def collection(
        self,
        collection_name: str,
    ) -> FakeCollectionReference:
        documents = self.collections.setdefault(
            collection_name,
            {},
        )

        return FakeCollectionReference(documents)


def create_stadium_document() -> StadiumDocument:
    now = datetime.now(timezone.utc)

    return StadiumDocument(
        name="잠실야구장",
        address="서울특별시 송파구 올림픽로 25",
        latitude=37.5122,
        longitude=127.0719,
        region="서울",
        created_at=now,
        updated_at=now,
    )


def create_game_document(
    *,
    home_team_id: str = "lg",
    away_team_id: str = "doosan",
    hour: int = 18,
) -> GameDocument:
    now = datetime.now(timezone.utc)

    return GameDocument(
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        stadium_id="jamsil",
        game_start_at=datetime(
            2026,
            8,
            15,
            hour,
            30,
            tzinfo=timezone.utc,
        ),
        status="SCHEDULED",
        home_score=None,
        away_score=None,
        result_text=None,
        created_at=now,
        updated_at=now,
    )


def test_stadium_repository_set_and_get_by_id() -> None:
    client = FakeFirestoreClient()
    repository = StadiumRepository(client=client)

    repository.set_stadium(
        "jamsil",
        create_stadium_document(),
    )

    stadium = repository.get_by_id("jamsil")

    assert stadium is not None
    assert stadium.stadium_id == "jamsil"
    assert stadium.name == "잠실야구장"
    assert stadium.region == "서울"


def test_stadium_repository_get_missing_returns_none() -> None:
    client = FakeFirestoreClient()
    repository = StadiumRepository(client=client)

    assert repository.get_by_id("missing") is None
    assert repository.exists("missing") is False


def test_stadium_repository_get_all_is_sorted_by_id() -> None:
    client = FakeFirestoreClient()
    repository = StadiumRepository(client=client)

    stadium = create_stadium_document()

    repository.set_stadium("sajik", stadium)
    repository.set_stadium("jamsil", stadium)

    stadiums = repository.get_all()

    assert [
        item.stadium_id
        for item in stadiums
    ] == [
        "jamsil",
        "sajik",
    ]


def test_stadium_repository_uses_camel_case_fields() -> None:
    client = FakeFirestoreClient()
    repository = StadiumRepository(client=client)

    repository.set_stadium(
        "jamsil",
        create_stadium_document(),
    )

    stored = client.collections["stadiums"]["jamsil"]

    assert "createdAt" in stored
    assert "updatedAt" in stored
    assert "created_at" not in stored
    assert isinstance(stored["createdAt"], datetime)


def test_game_repository_create_and_get_by_id() -> None:
    client = FakeFirestoreClient()
    repository = GameRepository(client=client)

    created = repository.create(
        "game_20260815_lg_doosan",
        create_game_document(),
    )

    game = repository.get_by_id(
        "game_20260815_lg_doosan"
    )

    assert created is True
    assert game is not None
    assert game.game_id == "game_20260815_lg_doosan"
    assert game.home_team_id == "lg"
    assert game.away_team_id == "doosan"


def test_game_repository_prevents_duplicate_id() -> None:
    client = FakeFirestoreClient()
    repository = GameRepository(client=client)

    game = create_game_document()

    first_created = repository.create(
        "game_20260815_lg_doosan",
        game,
    )
    second_created = repository.create(
        "game_20260815_lg_doosan",
        game,
    )

    assert first_created is True
    assert second_created is False


def test_game_repository_get_missing_returns_none() -> None:
    client = FakeFirestoreClient()
    repository = GameRepository(client=client)

    assert repository.get_by_id("missing") is None
    assert repository.exists("missing") is False


def test_game_repository_get_all_is_sorted_by_start_time() -> None:
    client = FakeFirestoreClient()
    repository = GameRepository(client=client)

    repository.create(
        "game_late",
        create_game_document(
            home_team_id="lg",
            away_team_id="doosan",
            hour=18,
        ),
    )
    repository.create(
        "game_early",
        create_game_document(
            home_team_id="nc",
            away_team_id="lotte",
            hour=14,
        ),
    )

    games = repository.get_all()

    assert [
        game.game_id
        for game in games
    ] == [
        "game_early",
        "game_late",
    ]


def test_game_repository_uses_camel_case_fields() -> None:
    client = FakeFirestoreClient()
    repository = GameRepository(client=client)

    repository.create(
        "game_20260815_lg_doosan",
        create_game_document(),
    )

    stored = client.collections["games"][
        "game_20260815_lg_doosan"
    ]

    assert "homeTeamId" in stored
    assert "awayTeamId" in stored
    assert "stadiumId" in stored
    assert "gameStartAt" in stored
    assert "createdAt" in stored
    assert "updatedAt" in stored

    assert "home_team_id" not in stored
    assert "game_start_at" not in stored
    assert isinstance(stored["gameStartAt"], datetime)
