import asyncio
from datetime import datetime, timezone
import logging

from fastapi import status

from app.core.exceptions import AppException
from app.external.tour_api.adapter import TourApiAdapter, tour_api_adapter
from app.models.place import Place
from app.repositories.favorite_collection_repository import (
    FavoriteCollectionRepository,
)
from app.schemas.favorite_collection import (
    FavoriteCollectionCreateRequest,
    FavoriteCollectionDocument,
    FavoriteCollectionItemDocument,
    FavoriteCollectionRecord,
    FavoriteCollectionResponse,
    FavoriteCollectionUpdateRequest,
    FavoritePlaceCollectionsResponse,
)


logger = logging.getLogger(__name__)


class FavoriteCollectionService:
    """개인 찜 컬렉션 비즈니스 로직을 담당합니다."""

    DEFAULT_COLLECTION_ID = "collection_saved"
    DEFAULT_COLLECTION_NAME = "저장됨"

    def __init__(
        self,
        repository: FavoriteCollectionRepository | None = None,
        place_adapter: TourApiAdapter | None = None,
    ) -> None:
        self._repository = (
            repository
            or FavoriteCollectionRepository()
        )
        self._place_adapter = place_adapter or tour_api_adapter

    def create_collection(
        self,
        *,
        user_id: str,
        request: FavoriteCollectionCreateRequest,
    ) -> FavoriteCollectionRecord:
        now = datetime.now(timezone.utc)

        document = FavoriteCollectionDocument(
            name=request.name,
            created_at=now,
            updated_at=now,
        )

        return self._repository.create(
            user_id=user_id,
            collection=document,
        )

    def ensure_default_collection(
        self,
        *,
        user_id: str,
    ) -> FavoriteCollectionRecord:
        """사용자의 기본 '저장됨' 컬렉션을 보장합니다."""
        now = datetime.now(timezone.utc)

        document = FavoriteCollectionDocument(
            name=self.DEFAULT_COLLECTION_NAME,
            is_default=True,
            created_at=now,
            updated_at=now,
        )

        return self._repository.create_if_absent(
            user_id=user_id,
            collection_id=self.DEFAULT_COLLECTION_ID,
            collection=document,
        )

    def get_collections(
        self,
        *,
        user_id: str,
    ) -> list[FavoriteCollectionRecord]:
        self.ensure_default_collection(
            user_id=user_id,
        )
        return self._repository.get_all(
            user_id=user_id,
        )

    async def get_collection_summary(
        self,
        *,
        user_id: str,
        collection: FavoriteCollectionRecord,
    ) -> FavoriteCollectionResponse:
        """실제 찜 장소 수와 첫 장소의 대표 정보를 조회합니다."""
        items = self._repository.get_items(
            user_id=user_id,
            collection_id=collection.collection_id,
        )

        place = None
        if items:
            first_item = items[0]
            place = first_item.place_snapshot

            if place is None:
                try:
                    place = await self._place_adapter.get_place_detail(
                        first_item.place_id.removeprefix("tour_")
                    )
                    self._repository.update_item_snapshot(
                        user_id=user_id,
                        collection_id=collection.collection_id,
                        place_id=first_item.place_id,
                        place_snapshot=place,
                    )
                except (AppException, ValueError):
                    place = None

        return FavoriteCollectionResponse(
            collection_id=collection.collection_id,
            name=collection.name,
            is_default=collection.is_default,
            thumbnail_url=(
                place.thumbnail_url if place is not None else None
            ),
            place_count=len(items),
            representative_place_name=(
                place.name if place is not None else None
            ),
            created_at=collection.created_at,
            updated_at=collection.updated_at,
        )

    async def get_collection_summaries(
        self,
        *,
        user_id: str,
        collections: list[FavoriteCollectionRecord],
    ) -> dict[str, FavoriteCollectionResponse]:
        """컬렉션별 요약 정보를 한 번씩 조회합니다."""
        summaries = await asyncio.gather(
            *(
                self.get_collection_summary(
                    user_id=user_id,
                    collection=collection,
                )
                for collection in collections
            )
        )
        return {
            summary.collection_id: summary
            for summary in summaries
        }

    async def get_collection_thumbnails(
        self,
        *,
        user_id: str,
        collections: list[FavoriteCollectionRecord],
    ) -> dict[str, str | None]:
        """기존 썸네일 조회 인터페이스를 유지합니다."""
        summaries = await self.get_collection_summaries(
            user_id=user_id,
            collections=collections,
        )
        return {
            collection_id: summary.thumbnail_url
            for collection_id, summary in summaries.items()
        }

    async def get_collection_places(
        self,
        *,
        user_id: str,
        collection_id: str,
    ) -> list[Place]:
        self._get_collection_or_raise(
            user_id=user_id,
            collection_id=collection_id,
        )
        items = self._repository.get_items(
            user_id=user_id,
            collection_id=collection_id,
        )
        places: list[Place] = []

        async def resolve(item: FavoriteCollectionItemDocument) -> Place | None:
            if item.place_snapshot is not None:
                return item.place_snapshot
            try:
                place = await self._place_adapter.get_place_detail(
                    item.place_id.removeprefix("tour_")
                )
                self._repository.update_item_snapshot(
                    user_id=user_id,
                    collection_id=collection_id,
                    place_id=item.place_id,
                    place_snapshot=place,
                )
                return place
            except (AppException, ValueError) as error:
                logger.warning(
                    "기존 찜 장소 상세조회 실패: collection_id=%s "
                    "place_id=%s error_type=%s",
                    collection_id,
                    item.place_id,
                    type(error).__name__,
                )
                return None

        resolved = await asyncio.gather(*(resolve(item) for item in items))
        places.extend(place for place in resolved if place is not None)
        return places

    def update_collection(
        self,
        *,
        user_id: str,
        collection_id: str,
        request: FavoriteCollectionUpdateRequest,
    ) -> FavoriteCollectionRecord:
        existing = self._get_collection_or_raise(
            user_id=user_id,
            collection_id=collection_id,
        )

        if (
            existing.is_default
            or collection_id == self.DEFAULT_COLLECTION_ID
        ):
            self._raise_default_collection_immutable()

        updated_at = datetime.now(timezone.utc)

        updated = self._repository.update_name(
            user_id=user_id,
            collection_id=collection_id,
            name=request.name,
            updated_at=updated_at,
        )

        if not updated:
            self._raise_not_found()

        return existing.model_copy(
            update={
                "name": request.name,
                "updated_at": updated_at,
            }
        )

    def delete_collection(
        self,
        *,
        user_id: str,
        collection_id: str,
    ) -> None:
        existing = self._get_collection_or_raise(
            user_id=user_id,
            collection_id=collection_id,
        )

        if (
            existing.is_default
            or collection_id == self.DEFAULT_COLLECTION_ID
        ):
            self._raise_default_collection_immutable()

        self._repository.delete(
            user_id=user_id,
            collection_id=collection_id,
        )

    async def save_item(
        self,
        *,
        user_id: str,
        collection_id: str,
        place_id: str,
    ) -> FavoriteCollectionItemDocument:
        """개인 컬렉션에 TourAPI 장소를 찜합니다."""

        self._get_collection_or_raise(
            user_id=user_id,
            collection_id=collection_id,
        )

        if not place_id.startswith("tour_"):
            raise AppException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="INVALID_FAVORITE_PLACE",
                message="TourAPI 장소만 찜할 수 있습니다.",
            )

        place = await self._place_adapter.get_place_detail(
            place_id.removeprefix("tour_")
        )

        item = FavoriteCollectionItemDocument(
            place_id=place_id,
            place_snapshot=place,
            created_at=datetime.now(timezone.utc),
        )

        return self._repository.save_item(
            user_id=user_id,
            collection_id=collection_id,
            item=item,
        )

    def delete_item(
        self,
        *,
        user_id: str,
        collection_id: str,
        place_id: str,
    ) -> None:
        """개인 컬렉션에서 찜 장소를 삭제합니다."""

        self._get_collection_or_raise(
            user_id=user_id,
            collection_id=collection_id,
        )

        deleted = self._repository.delete_item(
            user_id=user_id,
            collection_id=collection_id,
            place_id=place_id,
        )

        if not deleted:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="FAVORITE_COLLECTION_ITEM_NOT_FOUND",
                message="찜한 장소를 찾을 수 없습니다.",
            )

    def get_collections_for_place(
        self,
        *,
        user_id: str,
        place_id: str,
    ) -> FavoritePlaceCollectionsResponse:
        """장소가 저장된 현재 사용자의 컬렉션 ID를 조회합니다."""
        if not place_id.startswith("tour_"):
            raise AppException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                code="INVALID_FAVORITE_PLACE",
                message="TourAPI 장소만 찜할 수 있습니다.",
            )

        collections = self.get_collections(user_id=user_id)
        collection_ids = [
            collection.collection_id
            for collection in collections
            if self._repository.has_item(
                user_id=user_id,
                collection_id=collection.collection_id,
                place_id=place_id,
            )
        ]

        return FavoritePlaceCollectionsResponse(
            place_id=place_id,
            collection_ids=collection_ids,
            count=len(collection_ids),
        )

    def _get_collection_or_raise(
        self,
        *,
        user_id: str,
        collection_id: str,
    ) -> FavoriteCollectionRecord:
        collection = self._repository.get_by_id(
            user_id=user_id,
            collection_id=collection_id,
        )

        if collection is None:
            self._raise_not_found()

        return collection

    @staticmethod
    def _raise_default_collection_immutable() -> None:
        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="DEFAULT_FAVORITE_COLLECTION_IMMUTABLE",
            message=(
                "기본 찜 컬렉션은 이름을 변경하거나 "
                "삭제할 수 없습니다."
            ),
        )

    @staticmethod
    def _raise_not_found() -> None:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FAVORITE_COLLECTION_NOT_FOUND",
            message="찜 컬렉션을 찾을 수 없습니다.",
        )
