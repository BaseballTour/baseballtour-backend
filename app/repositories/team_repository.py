from google.cloud.firestore_v1.client import Client

from app.core.firebase import get_firestore_client
from app.schemas.team import (
    TeamDocument,
    TeamRecord,
)


class TeamRepository:
    """Firestore teams Collection 접근을 담당합니다."""

    COLLECTION_NAME = "teams"

    def __init__(
        self,
        client: Client | None = None,
    ) -> None:
        self._client = (
            client
            or get_firestore_client()
        )

        self._collection = (
            self._client.collection(
                self.COLLECTION_NAME
            )
        )

    def get_all(
        self,
    ) -> list[TeamRecord]:
        """전체 구단 목록을 조회합니다."""

        teams: list[TeamRecord] = []

        for document in self._collection.stream():
            data = document.to_dict() or {}

            teams.append(
                TeamRecord(
                    team_id=document.id,
                    **data,
                )
            )

        return sorted(
            teams,
            key=lambda team: team.team_id,
        )

    def get_by_id(
        self,
        team_id: str,
    ) -> TeamRecord | None:
        """문서 ID로 구단을 조회합니다."""

        document = (
            self._collection
            .document(team_id)
            .get()
        )

        if not document.exists:
            return None

        data = document.to_dict() or {}

        return TeamRecord(
            team_id=document.id,
            **data,
        )

    def exists(
        self,
        team_id: str,
    ) -> bool:
        """구단 문서가 존재하는지 확인합니다."""

        return (
            self._collection
            .document(team_id)
            .get()
            .exists
        )

    def set_team(
        self,
        team_id: str,
        team: TeamDocument,
    ) -> None:
        """구단 문서를 생성하거나 갱신합니다."""

        self._collection.document(
            team_id
        ).set(
            team.model_dump(
                by_alias=True,
                exclude_none=False,
            )
        )

    def update_logo_storage_path(
        self,
        team_id: str,
        storage_path: str,
    ) -> bool:
        """구단 로고 Storage 경로를 저장합니다."""

        reference = (
            self._collection.document(
                team_id
            )
        )

        snapshot = reference.get()

        if not snapshot.exists:
            return False

        reference.update(
            {
                "logoStoragePath": (
                    storage_path
                ),
                "logoUrl": None,
            }
        )

        return True
