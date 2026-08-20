from typing import Any

from google.cloud.exceptions import Conflict, NotFound
from google.cloud.firestore_v1.client import Client

from app.core.firebase import get_firestore_client
from app.schemas.user import UserDocument


class UserRepository:
    """Firestore users Collection 접근을 담당합니다."""

    COLLECTION_NAME = "users"

    def __init__(self, client: Client | None = None) -> None:
        self._client = client or get_firestore_client()
        self._collection = self._client.collection(self.COLLECTION_NAME)

    def get_by_id(self, user_id: str) -> UserDocument | None:
        """Firebase UID로 사용자 문서를 조회합니다."""

        document = self._collection.document(user_id).get()

        if not document.exists:
            return None

        data = document.to_dict() or {}
        return UserDocument.model_validate(data)

    def exists(self, user_id: str) -> bool:
        """사용자 문서가 존재하는지 확인합니다."""

        return self._collection.document(user_id).get().exists

    def create(self, user_id: str, user: UserDocument) -> bool:
        """사용자 문서를 최초 한 번만 생성합니다."""

        try:
            self._collection.document(user_id).create(
                user.model_dump(
                    by_alias=True,
                    exclude_none=False,
                )
            )
        except Conflict:
            return False

        return True

    def soft_delete(
        self,
        user_id: str,
        *,
        deleted_at,
    ) -> bool:
        """사용자를 탈퇴 상태로 soft delete합니다."""

        return self.update_fields(
            user_id,
            {
                "updatedAt": deleted_at,
                "deletedAt": deleted_at,
            },
        )

    def update_fields(
        self,
        user_id: str,
        fields: dict[str, Any],
    ) -> bool:
        """사용자 문서의 일부 필드를 수정합니다."""

        try:
            self._collection.document(user_id).update(fields)
        except NotFound:
            return False

        return True
