from typing import Any

from app.models.place import Place, PlaceCategory, PlaceSource


TOUR_API_CATEGORY_MAP: dict[str, PlaceCategory] = {
    "12": PlaceCategory.TOURIST_SPOT,
    "14": PlaceCategory.CULTURAL_FACILITY,
    "15": PlaceCategory.FESTIVAL,
    "28": PlaceCategory.OTHER,
    "32": PlaceCategory.ACCOMMODATION,
    "38": PlaceCategory.SHOPPING,
    "39": PlaceCategory.RESTAURANT,
}


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
    content_id = str(item.get("contentid", "")).strip()
    content_type_id = empty_string_to_none(
        item.get("contenttypeid")
    )

    return Place(
        place_id=f"tour_{content_id}",
        name=str(item.get("title", "")).strip(),
        category=get_place_category(content_type_id),
        latitude=float(item.get("mapy")),
        longitude=float(item.get("mapx")),
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
    return [
        tour_api_item_to_place(item)
        for item in items
    ]
