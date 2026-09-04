from google.cloud.firestore_v1.client import Client

from app.core.firebase import get_firestore_client
from app.schemas.term import (
    TermDocument,
    TermRecord,
)


class TermRepository:
    """Firestore terms Collection 접근을 담당합니다."""

    COLLECTION_NAME = "terms"

    def __init__(
        self,
        client: Client | None = None,
    ) -> None:
        self._client = client or get_firestore_client()
        self._collection = self._client.collection(
            self.COLLECTION_NAME
        )

    def set_term(
        self,
        term_id: str,
        term: TermDocument,
    ) -> None:
        """약관 문서를 생성하거나 덮어씁니다."""

        self._collection.document(
            term_id
        ).set(
            term.model_dump(
                by_alias=True,
            )
        )

    def get_active_terms(
        self,
    ) -> list[TermRecord]:
        """현재 활성 상태인 약관 목록을 조회합니다."""

        terms: list[TermRecord] = []

        for document in self._collection.stream():
            if not document.exists:
                continue

            data = document.to_dict() or {}
            term = TermDocument.model_validate(data)

            if not term.active:
                continue

            terms.append(
                TermRecord(
                    term_id=document.id,
                    **term.model_dump(),
                )
            )

        term_order = {
            "TERMS_OF_SERVICE": 1,
            "PRIVACY_POLICY": 2,
            "LOCATION_BASED_SERVICE": 3,
            "MARKETING": 4,
        }

        terms.sort(
            key=lambda term: term_order[
                term.term_code.value
            ],
        )

        return terms
