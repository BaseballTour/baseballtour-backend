from datetime import datetime

from google.api_core.exceptions import AlreadyExists
from google.cloud.exceptions import NotFound
from google.cloud.firestore_v1.client import Client

from app.core.firebase import get_firestore_client
from app.core.ids import new_prefixed_id
from app.schemas.favorite_collection import (
    FavoriteCollectionDocument,
    FavoriteCollectionItemDocument,
    FavoriteCollectionRecord,
)


class FavoriteCollectionRepository:
    """사용자 개인 찜 컬렉션 Firestore 접근을 담당합니다."""

    USERS_COLLECTION_NAME = "users"
    SUBCOLLECTION_NAME = "favoriteCollections"
    ITEMS_SUBCOLLECTION_NAME = "items"

    def __init__(
        self,
        client: Client | None = None,
    ) -> None:
        self._client = client or get_firestore_client()

    def _get_collection(
        self,
        user_id: str,
    ):
        return (
            self._client
            .collection(self.USERS_COLLECTION_NAME)
            .document(user_id)
            .collection(self.SUBCOLLECTION_NAME)
        )

    def _get_items_collection(
        self,
        *,
        user_id: str,
        collection_id: str,
    ):
        return (
            self._get_collection(user_id)
            .document(collection_id)
            .collection(self.ITEMS_SUBCOLLECTION_NAME)
        )

    def create(
        self,
        *,
        user_id: str,
        collection: FavoriteCollectionDocument,
    ) -> FavoriteCollectionRecord:
        """개인 찜 컬렉션을 생성합니다."""

        document_reference = (
            self._get_collection(user_id)
            .document(new_prefixed_id("collection"))
        )

        document_reference.set(
            collection.model_dump(
                by_alias=True,
                exclude_none=False,
            )
        )

        return FavoriteCollectionRecord(
            collection_id=document_reference.id,
            **collection.model_dump(),
        )

    def get_all(
        self,
        *,
        user_id: str,
    ) -> list[FavoriteCollectionRecord]:
        """사용자의 개인 찜 컬렉션을 조회합니다."""

        records: list[FavoriteCollectionRecord] = []

        for snapshot in self._get_collection(
            user_id
        ).stream():
            data = snapshot.to_dict() or {}

            records.append(
                FavoriteCollectionRecord(
                    collection_id=snapshot.id,
                    **data,
                )
            )

        return sorted(
            records,
            key=lambda record: record.created_at,
        )

    def get_by_id(
        self,
        *,
        user_id: str,
        collection_id: str,
    ) -> FavoriteCollectionRecord | None:
        """개인 찜 컬렉션을 ID로 조회합니다."""

        snapshot = (
            self._get_collection(user_id)
            .document(collection_id)
            .get()
        )

        if not snapshot.exists:
            return None

        data = snapshot.to_dict() or {}

        return FavoriteCollectionRecord(
            collection_id=collection_id,
            **data,
        )

    def update_name(
        self,
        *,
        user_id: str,
        collection_id: str,
        name: str,
        updated_at: datetime,
    ) -> bool:
        """개인 찜 컬렉션 이름을 변경합니다."""

        try:
            (
                self._get_collection(user_id)
                .document(collection_id)
                .update(
                    {
                        "name": name,
                        "updatedAt": updated_at,
                    }
                )
            )
        except NotFound:
            return False

        return True

    def delete(
        self,
        *,
        user_id: str,
        collection_id: str,
    ) -> None:
        """하위 찜 Item을 정리한 뒤 컬렉션을 삭제합니다."""

        items = self._get_items_collection(
            user_id=user_id,
            collection_id=collection_id,
        )

        snapshots = list(items.stream())

        for snapshot in snapshots:
            items.document(snapshot.id).delete()

        (
            self._get_collection(user_id)
            .document(collection_id)
            .delete()
        )

    def save_item(
        self,
        *,
        user_id: str,
        collection_id: str,
        item: FavoriteCollectionItemDocument,
    ) -> FavoriteCollectionItemDocument:
        """찜 장소를 중복 없이 저장합니다."""

        document_reference = (
            self._get_items_collection(
                user_id=user_id,
                collection_id=collection_id,
            )
            .document(item.place_id)
        )

        try:
            document_reference.create(
                item.model_dump(
                    by_alias=True,
                    exclude_none=False,
                )
            )
        except AlreadyExists:
            snapshot = document_reference.get()
            data = snapshot.to_dict() or {}

            return FavoriteCollectionItemDocument.model_validate(
                data
            )

        return item

    def get_items(
        self,
        *,
        user_id: str,
        collection_id: str,
    ) -> list[FavoriteCollectionItemDocument]:
        """컬렉션의 찜 장소 목록을 조회합니다."""

        items: list[FavoriteCollectionItemDocument] = []

        for snapshot in self._get_items_collection(
            user_id=user_id,
            collection_id=collection_id,
        ).stream():
            data = snapshot.to_dict() or {}

            items.append(
                FavoriteCollectionItemDocument.model_validate(
                    data
                )
            )

        return sorted(
            items,
            key=lambda item: item.created_at,
        )

    def delete_item(
        self,
        *,
        user_id: str,
        collection_id: str,
        place_id: str,
    ) -> bool:
        """컬렉션에서 찜 장소를 삭제합니다."""

        document_reference = (
            self._get_items_collection(
                user_id=user_id,
                collection_id=collection_id,
            )
            .document(place_id)
        )

        snapshot = document_reference.get()

        if not snapshot.exists:
            return False

        document_reference.delete()

        return True

    def delete_all_by_user_id(
        self,
        *,
        user_id: str,
    ) -> int:
        """사용자의 모든 개인 찜 컬렉션과 하위 Item을 삭제합니다."""

        collection = self._get_collection(user_id)
        snapshots = list(collection.stream())

        for snapshot in snapshots:
            self.delete(
                user_id=user_id,
                collection_id=snapshot.id,
            )

        return len(snapshots)
