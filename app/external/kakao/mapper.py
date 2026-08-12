from typing import Any

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
