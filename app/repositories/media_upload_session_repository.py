from datetime import datetime
from hashlib import sha256

from google.cloud.firestore_v1.client import Client

from app.core.firebase import get_firestore_client


class MediaUploadSessionRepository:
    """커버이미지 업로드 발급 당시의 상태를 보관합니다."""

    COLLECTION_NAME = "mediaUploadSessions"

    def __init__(self, client: Client | None = None) -> None:
        self._client = client or get_firestore_client()
        self._collection = self._client.collection(
            self.COLLECTION_NAME
        )

    @staticmethod
    def _document_id(storage_path: str) -> str:
        return sha256(storage_path.encode("utf-8")).hexdigest()

    def create(
        self,
        *,
        user_id: str,
        trip_id: str,
        storage_path: str,
        expected_storage_path: str | None,
        content_type: str,
        created_at: datetime,
        expires_at: datetime,
    ) -> None:
        self._collection.document(
            self._document_id(storage_path)
        ).create(
            {
                "userId": user_id,
                "tripId": trip_id,
                "storagePath": storage_path,
                "expectedCoverImageStoragePath": expected_storage_path,
                "contentType": content_type,
                "createdAt": created_at,
                "expiresAt": expires_at,
            }
        )

    def get_by_storage_path(
        self,
        storage_path: str,
    ) -> dict | None:
        snapshot = self._collection.document(
            self._document_id(storage_path)
        ).get()

        if not snapshot.exists:
            return None

        return snapshot.to_dict() or {}
