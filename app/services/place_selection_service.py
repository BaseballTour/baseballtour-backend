from datetime import datetime, timezone

from fastapi import status

from app.core.exceptions import AppException
from app.external.tour_api.adapter import tour_api_adapter
from app.repositories.favorite_collection_repository import (
    FavoriteCollectionRepository,
)
from app.repositories.game_repository import GameRepository
from app.repositories.place_selection_repository import (
    PlaceSelectionRepository,
)
from app.repositories.stadium_repository import StadiumRepository
from app.repositories.trip_repository import TripRepository
from app.schemas.place_selection import (
    PlaceSelectionCreateRequest,
    PlaceSelectionDocument,
    PlaceSelectionRecord,
)
from app.schemas.trip import TripRecord


REGION_ADDRESS_PREFIXES: dict[str, tuple[str, ...]] = {
    "서울": ("서울특별시", "서울"),
    "인천": ("인천광역시", "인천"),
    "경기": ("경기도", "경기"),
    "대전": ("대전광역시", "대전"),
    "광주": ("광주광역시", "광주"),
    "대구": ("대구광역시", "대구"),
    "부산": ("부산광역시", "부산"),
    "경남": ("경상남도", "경남"),
}


class PlaceSelectionService:
    """여행별 장소 선택 비즈니스 로직을 담당합니다."""

    def __init__(
        self,
        place_selection_repository: PlaceSelectionRepository | None = None,
        trip_repository: TripRepository | None = None,
        favorite_collection_repository: (
            FavoriteCollectionRepository | None
        ) = None,
        game_repository: GameRepository | None = None,
        stadium_repository: StadiumRepository | None = None,
        place_adapter=None,
    ) -> None:
        self._place_selection_repository = (
            place_selection_repository
            or PlaceSelectionRepository()
        )
        self._trip_repository = (
            trip_repository
            or TripRepository()
        )
        self._favorite_collection_repository = (
            favorite_collection_repository
            or FavoriteCollectionRepository()
        )
        self._game_repository = (
            game_repository
            or GameRepository()
        )
        self._stadium_repository = (
            stadium_repository
            or StadiumRepository()
        )
        self._place_adapter = (
            place_adapter
            or tour_api_adapter
        )

    def create_selection(
        self,
        *,
        user_id: str,
        trip_id: str,
        request: PlaceSelectionCreateRequest,
    ) -> PlaceSelectionRecord:
        """로그인 사용자의 여행에 장소를 선택합니다."""

        self._get_owned_trip_or_raise(
            user_id=user_id,
            trip_id=trip_id,
        )

        selection = PlaceSelectionDocument(
            place_id=request.place_id,
            is_required=request.is_required,
            created_at=datetime.now(timezone.utc),
        )

        created = self._place_selection_repository.create(
            trip_id=trip_id,
            selection=selection,
        )

        if created is None:
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="PLACE_SELECTION_ALREADY_EXISTS",
                message="이미 선택된 장소입니다.",
            )

        return created

    def get_selections(
        self,
        *,
        user_id: str,
        trip_id: str,
    ) -> list[PlaceSelectionRecord]:
        """로그인 사용자의 여행에 선택된 장소 목록을 조회합니다."""

        self._get_owned_trip_or_raise(
            user_id=user_id,
            trip_id=trip_id,
        )

        return self._place_selection_repository.get_all(
            trip_id=trip_id,
        )

    def update_required(
        self,
        *,
        user_id: str,
        trip_id: str,
        place_id: str,
        is_required: bool,
    ) -> PlaceSelectionRecord:
        """여행 후보의 필수 방문 여부를 변경합니다."""

        self._get_owned_trip_or_raise(
            user_id=user_id,
            trip_id=trip_id,
        )

        updated = (
            self._place_selection_repository.update_required(
                trip_id=trip_id,
                place_id=place_id,
                is_required=is_required,
            )
        )

        if updated is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="PLACE_SELECTION_NOT_FOUND",
                message="선택된 장소를 찾을 수 없습니다.",
            )

        return updated

    def delete_selection(
        self,
        *,
        user_id: str,
        trip_id: str,
        place_id: str,
    ) -> None:
        """로그인 사용자의 여행에서 선택된 장소를 삭제합니다."""

        self._get_owned_trip_or_raise(
            user_id=user_id,
            trip_id=trip_id,
        )

        deleted = self._place_selection_repository.delete(
            trip_id=trip_id,
            place_id=place_id,
        )

        if not deleted:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="PLACE_SELECTION_NOT_FOUND",
                message="선택된 장소를 찾을 수 없습니다.",
            )

    async def import_from_favorite_collection(
        self,
        *,
        user_id: str,
        trip_id: str,
        collection_id: str,
    ) -> list[PlaceSelectionRecord]:
        """개인 찜 컬렉션의 같은 지역 장소를 여행 후보로 불러옵니다."""

        trip = self._get_owned_trip_or_raise(
            user_id=user_id,
            trip_id=trip_id,
        )

        collection = (
            self._favorite_collection_repository.get_by_id(
                user_id=user_id,
                collection_id=collection_id,
            )
        )

        if collection is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="FAVORITE_COLLECTION_NOT_FOUND",
                message="찜 컬렉션을 찾을 수 없습니다.",
            )

        game = self._game_repository.get_by_id(
            trip.game_id
        )

        if game is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="GAME_NOT_FOUND",
                message="경기 정보를 찾을 수 없습니다.",
            )

        stadium = self._stadium_repository.get_by_id(
            game.stadium_id
        )

        if stadium is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="STADIUM_NOT_FOUND",
                message="구장 정보를 찾을 수 없습니다.",
            )

        favorite_items = (
            self._favorite_collection_repository.get_items(
                user_id=user_id,
                collection_id=collection_id,
            )
        )

        existing_place_ids = {
            selection.place_id
            for selection
            in self._place_selection_repository.get_all(
                trip_id=trip_id
            )
        }

        imported: list[PlaceSelectionRecord] = []

        for item in favorite_items:
            place_id = item.place_id

            if place_id in existing_place_ids:
                continue

            if (
                not place_id.startswith("tour_")
                or not place_id.removeprefix("tour_")
            ):
                continue

            content_id = place_id.removeprefix(
                "tour_"
            )

            try:
                place = await self._place_adapter.get_place_detail(
                    content_id
                )
            except (ValueError, AppException):
                continue

            if not self._matches_stadium_region(
                address=place.address,
                stadium_region=stadium.region,
            ):
                continue

            selection = PlaceSelectionDocument(
                place_id=place_id,
                is_required=False,
                created_at=datetime.now(timezone.utc),
            )

            created = (
                self._place_selection_repository.create(
                    trip_id=trip_id,
                    selection=selection,
                )
            )

            if created is None:
                continue

            imported.append(created)
            existing_place_ids.add(place_id)

        return imported

    @staticmethod
    def _matches_stadium_region(
        *,
        address: str,
        stadium_region: str,
    ) -> bool:
        """장소 주소와 구장 시·도 지역이 같은지 판정합니다."""

        normalized_address = " ".join(
            address.split()
        )

        if not normalized_address:
            return False

        region = stadium_region.strip()

        if not region:
            return False

        prefixes = REGION_ADDRESS_PREFIXES.get(
            region,
            (region,),
        )

        return any(
            normalized_address == prefix
            or normalized_address.startswith(
                f"{prefix} "
            )
            for prefix in prefixes
        )

    def _get_owned_trip_or_raise(
        self,
        *,
        user_id: str,
        trip_id: str,
    ) -> TripRecord:
        trip = self._trip_repository.get_by_id(
            trip_id
        )

        if trip is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="TRIP_NOT_FOUND",
                message="여행 정보를 찾을 수 없습니다.",
            )

        if trip.user_id != user_id:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="TRIP_ACCESS_DENIED",
                message="해당 여행에 접근할 권한이 없습니다.",
            )

        return trip
