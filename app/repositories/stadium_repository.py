from google.cloud.firestore_v1.client import Client

from app.core.firebase import get_firestore_client
from app.schemas.stadium import (
    StadiumDocument,
    StadiumResponse,
)


class StadiumRepository:
    """Firestore stadiums Collection 접근을 담당합니다."""

    COLLECTION_NAME = "stadiums"

    def __init__(self, client: Client | None = None) -> None:
        self._client = client or get_firestore_client()
        self._collection = self._client.collection(
            self.COLLECTION_NAME
        )

    def get_all(self) -> list[StadiumResponse]:
        """전체 구장 목록을 조회합니다."""

        stadiums: list[StadiumResponse] = []

        for document in self._collection.stream():
            data = document.to_dict() or {}

            stadiums.append(
                StadiumResponse(
                    stadium_id=document.id,
                    **data,
                )
            )

        return sorted(
            stadiums,
            key=lambda stadium: stadium.stadium_id,
        )

    def get_by_id(
        self,
        stadium_id: str,
    ) -> StadiumResponse | None:
        """문서 ID로 구장을 조회합니다."""

        document = self._collection.document(
            stadium_id
        ).get()

        if not document.exists:
            return None

        data = document.to_dict() or {}

        return StadiumResponse(
            stadium_id=document.id,
            **data,
        )

    def exists(self, stadium_id: str) -> bool:
        """구장 문서가 존재하는지 확인합니다."""

        return self._collection.document(
            stadium_id
        ).get().exists

    def set_stadium(
        self,
        stadium_id: str,
        stadium: StadiumDocument,
    ) -> None:
        """구장 문서를 생성하거나 같은 ID의 문서를 갱신합니다."""

        self._collection.document(
            stadium_id
        ).set(
            stadium.model_dump(
                by_alias=True,
                exclude_none=False,
            )
        )
