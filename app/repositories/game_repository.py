from google.cloud.exceptions import Conflict
from google.cloud.firestore_v1.client import Client

from app.core.firebase import get_firestore_client
from app.schemas.game import (
    GameDocument,
    GameRecord,
)


class GameRepository:
    """Firestore games Collection 접근을 담당합니다."""

    COLLECTION_NAME = "games"

    def __init__(self, client: Client | None = None) -> None:
        self._client = client or get_firestore_client()
        self._collection = self._client.collection(
            self.COLLECTION_NAME
        )

    def get_all(self) -> list[GameRecord]:
        """전체 경기 목록을 경기 시작시간 순으로 조회합니다."""

        games: list[GameRecord] = []

        for document in self._collection.stream():
            data = document.to_dict() or {}

            games.append(
                GameRecord(
                    game_id=document.id,
                    **data,
                )
            )

        return sorted(
            games,
            key=lambda game: game.game_start_at,
        )

    def get_by_id(
        self,
        game_id: str,
    ) -> GameRecord | None:
        """문서 ID로 경기를 조회합니다."""

        document = self._collection.document(
            game_id
        ).get()

        if not document.exists:
            return None

        data = document.to_dict() or {}

        return GameRecord(
            game_id=document.id,
            **data,
        )

    def exists(self, game_id: str) -> bool:
        """경기 문서가 존재하는지 확인합니다."""

        return self._collection.document(
            game_id
        ).get().exists

    def create(
        self,
        game_id: str,
        game: GameDocument,
    ) -> bool:
        """동일한 ID가 없을 때만 경기 문서를 생성합니다."""

        try:
            self._collection.document(
                game_id
            ).create(
                game.model_dump(
                    by_alias=True,
                    exclude_none=False,
                )
            )
        except Conflict:
            return False

        return True

    def set_game(
        self,
        game_id: str,
        game: GameDocument,
    ) -> None:
        """경기 문서를 생성하거나 같은 ID의 문서를 갱신합니다."""

        self._collection.document(
            game_id
        ).set(
            game.model_dump(
                by_alias=True,
                exclude_none=False,
            )
        )
