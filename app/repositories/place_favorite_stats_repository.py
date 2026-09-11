from datetime import datetime

from google.cloud.firestore_v1.client import Client
from google.cloud.firestore_v1.transaction import transactional

from app.core.firebase import get_firestore_client


class PlaceFavoriteStatsRepository:
    """장소를 찜한 고유 사용자 수를 관리합니다."""

    COLLECTION_NAME = "placeFavoriteStats"
    USERS_SUBCOLLECTION_NAME = "users"

    def __init__(self, client: Client | None = None) -> None:
        self._client = client or get_firestore_client()
        self._collection = self._client.collection(self.COLLECTION_NAME)

    def get_count(self, place_id: str) -> int:
        snapshot = self._collection.document(place_id).get()
        if not snapshot.exists:
            return 0
        value = (snapshot.to_dict() or {}).get("favoriteCount", 0)
        return max(0, int(value or 0))

    def get_counts(self, place_ids: list[str]) -> dict[str, int]:
        unique_ids = list(dict.fromkeys(place_ids))
        if not unique_ids:
            return {}
        references = [self._collection.document(place_id) for place_id in unique_ids]
        snapshots = {
            snapshot.id: snapshot
            for snapshot in self._client.get_all(references)
        }
        return {
            place_id: max(
                0,
                int(
                    (
                        (snapshots.get(place_id).to_dict() or {}).get(
                            "favoriteCount",
                            0,
                        )
                    )
                    if snapshots.get(place_id) is not None
                    and snapshots[place_id].exists
                    else 0
                ),
            )
            for place_id in unique_ids
        }

    def add_user(
        self,
        *,
        place_id: str,
        user_id: str,
        updated_at: datetime,
    ) -> int:
        stats_reference = self._collection.document(place_id)
        user_reference = stats_reference.collection(
            self.USERS_SUBCOLLECTION_NAME
        ).document(user_id)
        transaction = self._client.transaction()

        @transactional
        def update(transaction):
            user_snapshot = user_reference.get(transaction=transaction)
            stats_snapshot = stats_reference.get(transaction=transaction)
            current = (
                int(
                    (stats_snapshot.to_dict() or {}).get(
                        "favoriteCount",
                        0,
                    )
                )
                if stats_snapshot.exists
                else 0
            )
            if user_snapshot.exists:
                return max(0, current)
            next_count = current + 1
            transaction.set(user_reference, {"createdAt": updated_at})
            transaction.set(
                stats_reference,
                {"favoriteCount": next_count, "updatedAt": updated_at},
                merge=True,
            )
            return next_count

        return update(transaction)

    def remove_user(
        self,
        *,
        place_id: str,
        user_id: str,
        updated_at: datetime,
    ) -> int:
        stats_reference = self._collection.document(place_id)
        user_reference = stats_reference.collection(
            self.USERS_SUBCOLLECTION_NAME
        ).document(user_id)
        transaction = self._client.transaction()

        @transactional
        def update(transaction):
            user_snapshot = user_reference.get(transaction=transaction)
            stats_snapshot = stats_reference.get(transaction=transaction)
            current = (
                int(
                    (stats_snapshot.to_dict() or {}).get(
                        "favoriteCount",
                        0,
                    )
                )
                if stats_snapshot.exists
                else 0
            )
            if not user_snapshot.exists:
                return max(0, current)
            next_count = max(0, current - 1)
            transaction.delete(user_reference)
            transaction.set(
                stats_reference,
                {"favoriteCount": next_count, "updatedAt": updated_at},
                merge=True,
            )
            return next_count

        return update(transaction)
