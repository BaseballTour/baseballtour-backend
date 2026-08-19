from google.cloud.firestore_v1.client import Client

from app.core.firebase import get_firestore_client
from app.schemas.term import (
    TermAgreementDocument,
    TermCode,
)


class TermAgreementRepository:
    """사용자별 약관 동의 기록 접근을 담당합니다."""

    USERS_COLLECTION_NAME = "users"
    SUBCOLLECTION_NAME = "termAgreements"

    def __init__(
        self,
        client: Client | None = None,
    ) -> None:
        self._client = client or get_firestore_client()

    def save_all(
        self,
        user_id: str,
        agreements: dict[
            TermCode,
            TermAgreementDocument,
        ],
    ) -> None:
        """여러 약관 동의를 하나의 batch로 저장합니다."""

        agreement_collection = (
            self._client
            .collection(self.USERS_COLLECTION_NAME)
            .document(user_id)
            .collection(self.SUBCOLLECTION_NAME)
        )

        batch = self._client.batch()

        for term_code, agreement in agreements.items():
            document = agreement_collection.document(
                term_code.value
            )

            batch.set(
                document,
                agreement.model_dump(
                    by_alias=True,
                    exclude_none=False,
                ),
            )

        batch.commit()
