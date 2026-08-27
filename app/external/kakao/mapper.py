from typing import Any

from app.schemas.accommodation import (
    AccommodationCandidate,
    AccommodationSelectionType,
)

from app.models.place import PlaceCategory


KAKAO_CATEGORY_MAP: dict[str, PlaceCategory] = {
    "AT4": PlaceCategory.TOURIST_SPOT,
    "CT1": PlaceCategory.CULTURAL_FACILITY,
    "AD5": PlaceCategory.ACCOMMODATION,
    "FD6": PlaceCategory.RESTAURANT,
    "CE7": PlaceCategory.CAFE,
}


def kakao_category_to_place_category(
    category_group_code: Any,
) -> PlaceCategory:
    return KAKAO_CATEGORY_MAP.get(
        str(category_group_code or "").strip(),
        PlaceCategory.OTHER,
    )


def kakao_address(item: dict[str, Any]) -> str:
    return str(
        item.get("road_address_name") or item.get("address_name") or ""
    ).strip()


def kakao_place_to_accommodation(
    item: dict[str, Any],
) -> AccommodationCandidate:
    """Kakao 키워드 장소 결과를 숙소 Anchor 후보로 변환합니다."""

    return AccommodationCandidate(
        kakao_place_id=str(item.get("id") or "").strip() or None,
        name=str(item.get("place_name") or "").strip(),
        address=kakao_address(item),
        road_address_name=(
            str(item.get("road_address_name") or "").strip() or None
        ),
        latitude=float(item.get("y")),
        longitude=float(item.get("x")),
        phone=str(item.get("phone") or "").strip() or None,
        place_url=str(item.get("place_url") or "").strip() or None,
        category_name=(
            str(item.get("category_name") or "").strip() or None
        ),
        selection_type=AccommodationSelectionType.KAKAO_PLACE,
    )


def kakao_address_to_accommodation(
    item: dict[str, Any],
    *,
    latitude: float,
    longitude: float,
) -> AccommodationCandidate:
    """Kakao 좌표→주소 결과를 지도 선택 숙소 후보로 변환합니다."""

    road = item.get("road_address")
    address_item = item.get("address")
    road = road if isinstance(road, dict) else {}
    address_item = address_item if isinstance(address_item, dict) else {}
    road_address = str(road.get("address_name") or "").strip()
    address = road_address or str(address_item.get("address_name") or "").strip()
    building_name = str(road.get("building_name") or "").strip()
    return AccommodationCandidate(
        kakao_place_id=None,
        name=building_name or address,
        address=address,
        road_address_name=road_address or None,
        latitude=latitude,
        longitude=longitude,
        selection_type=AccommodationSelectionType.MAP_POINT,
    )
