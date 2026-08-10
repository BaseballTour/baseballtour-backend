from typing import Any
import logging
from typing import Any

from app.models.place import Place, PlaceCategory, PlaceSource

logger = logging.getLogger(__name__)

TOUR_API_CATEGORY_MAP: dict[str, PlaceCategory] = {
    "12": PlaceCategory.TOURIST_SPOT,
    "14": PlaceCategory.CULTURAL_FACILITY,
    "15": PlaceCategory.FESTIVAL,
    "28": PlaceCategory.ACTIVITY,
    "32": PlaceCategory.ACCOMMODATION,
    "38": PlaceCategory.SHOPPING,
    "39": PlaceCategory.RESTAURANT,
}



def get_tour_api_content_type_id(
    category: PlaceCategory | None,
) -> str | None:
    if category is None:
        return None

    for content_type_id, mapped_category in TOUR_API_CATEGORY_MAP.items():
        if mapped_category == category:
            return content_type_id

    return None


def get_place_category(content_type_id: str | None) -> PlaceCategory:
    if not content_type_id:
        return PlaceCategory.OTHER

    return TOUR_API_CATEGORY_MAP.get(
        content_type_id,
        PlaceCategory.OTHER,
    )


def combine_address(
    address1: str | None,
    address2: str | None,
) -> str:
    address_parts = [
        part.strip()
        for part in [address1, address2]
        if part and part.strip()
    ]

    return " ".join(address_parts)


def empty_string_to_none(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    return text


def tour_api_item_to_place(item: dict[str, Any]) -> Place:
    content_id = get_required_text(
        item,
        "contentid",
    )

    name = get_required_text(
        item,
        "title",
    )

    latitude = get_required_coordinate(
        item,
        "mapy",
        minimum=-90,
        maximum=90,
    )

    longitude = get_required_coordinate(
        item,
        "mapx",
        minimum=-180,
        maximum=180,
    )

    content_type_id = empty_string_to_none(
        item.get("contenttypeid")
    )

    return Place(
        place_id=f"tour_{content_id}",
        name=name,
        category=get_place_category(content_type_id),
        latitude=latitude,
        longitude=longitude,
        address=combine_address(
            item.get("addr1"),
            item.get("addr2"),
        ),
        postal_code=empty_string_to_none(
            item.get("zipcode")
        ),
        telephone=empty_string_to_none(
            item.get("tel")
        ),
        thumbnail_url=empty_string_to_none(
            item.get("firstimage")
        ),
        overview=empty_string_to_none(item.get("overview")),
        open_time=empty_string_to_none(item.get("openTime")),
        close_time=empty_string_to_none(item.get("closeTime")),
        closed_days_text=empty_string_to_none(
            item.get("closedDaysText")
        ),
        distance_meters=(
            float(item["dist"])
            if empty_string_to_none(item.get("dist"))
            else None
        ),
        source=PlaceSource.TOUR_API,
        source_content_id=content_id,
        content_type_id=content_type_id,
        area_code=empty_string_to_none(
            item.get("areacode")
        ),
        sigungu_code=empty_string_to_none(
            item.get("sigungucode")
        ),
        category_code1=empty_string_to_none(
            item.get("cat1")
        ),
        category_code2=empty_string_to_none(
            item.get("cat2")
        ),
        category_code3=empty_string_to_none(
            item.get("cat3")
        ),
    )


def tour_api_items_to_places(
    items: list[dict[str, Any]],
) -> list[Place]:
    places: list[Place] = []

    for item in items:
        try:
            place = tour_api_item_to_place(item)
        except (TypeError, ValueError) as exc:
            logger.warning(
                "유효하지 않은 TourAPI 장소를 제외합니다: "
                "contentid=%r reason=%s",
                item.get("contentid"),
                exc,
            )
            continue

        places.append(place)

    return places


def deduplicate_places(places: list[Place]) -> list[Place]:
    """같은 내부 장소 ID는 거리와 정보가 더 좋은 항목 하나만 유지한다."""
    unique: dict[str, Place] = {}

    for place in places:
        current = unique.get(place.place_id)
        if current is None:
            unique[place.place_id] = place
            continue

        current_distance = (
            current.distance_meters
            if current.distance_meters is not None
            else float("inf")
        )
        candidate_distance = (
            place.distance_meters
            if place.distance_meters is not None
            else float("inf")
        )
        if candidate_distance < current_distance:
            unique[place.place_id] = place
        elif current.thumbnail_url is None and place.thumbnail_url:
            unique[place.place_id] = place

    return list(unique.values())


def get_required_text(
    item: dict[str, Any],
    field: str,
) -> str:
    value = empty_string_to_none(item.get(field))

    if value is None:
        raise ValueError(
            f"TourAPI 장소의 {field} 값이 없습니다."
        )

    return value


def get_required_coordinate(
    item: dict[str, Any],
    field: str,
    *,
    minimum: float,
    maximum: float,
) -> float:
    raw_value = get_required_text(item, field)

    try:
        value = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"TourAPI 장소의 {field} 값이 숫자가 아닙니다."
        ) from exc

    if not minimum <= value <= maximum:
        raise ValueError(
            f"TourAPI 장소의 {field} 값이 "
            f"허용 범위를 벗어났습니다."
        )

    return value
