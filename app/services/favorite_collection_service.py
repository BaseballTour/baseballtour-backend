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
    FavoriteCollectionUpdateRequest,
)


logger = logging.getLogger(__name__)


class FavoriteCollectionService:
    """개인 찜 컬렉션 비즈니스 로직을 담당합니다."""

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

    def get_collections(
        self,
        *,
        user_id: str,
    ) -> list[FavoriteCollectionRecord]:
        return self._repository.get_all(
            user_id=user_id,
        )

    async def get_collection_thumbnails(
        self,
        *,
        user_id: str,
        collections: list[FavoriteCollectionRecord],
    ) -> dict[str, str | None]:
        async def load(collection: FavoriteCollectionRecord):
            items = self._repository.get_items(
                user_id=user_id,
                collection_id=collection.collection_id,
            )
            if not items:
                return collection.collection_id, None
            if items[0].place_snapshot is not None:
                return (
                    collection.collection_id,
                    items[0].place_snapshot.thumbnail_url,
                )
            try:
                place = await self._place_adapter.get_place_detail(
                    items[0].place_id.removeprefix("tour_")
                )
                self._repository.update_item_snapshot(
                    user_id=user_id,
                    collection_id=collection.collection_id,
                    place_id=items[0].place_id,
                    place_snapshot=place,
                )
                return collection.collection_id, place.thumbnail_url
            except (AppException, ValueError):
                return collection.collection_id, None

        return dict(await asyncio.gather(*(load(item) for item in collections)))

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
        self._get_collection_or_raise(
            user_id=user_id,
            collection_id=collection_id,
        )

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
    def _raise_not_found() -> None:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FAVORITE_COLLECTION_NOT_FOUND",
            message="찜 컬렉션을 찾을 수 없습니다.",
        )
