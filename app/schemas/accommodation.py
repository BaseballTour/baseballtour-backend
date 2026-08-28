from enum import Enum

from pydantic import Field

from app.schemas.base import ApiModel


class AccommodationSelectionType(str, Enum):
    KAKAO_PLACE = "KAKAO_PLACE"
    MAP_POINT = "MAP_POINT"


class AccommodationCandidate(ApiModel):
    """검색 결과 또는 지도에서 선택한 숙소 정보."""

    kakao_place_id: str | None = None
    name: str = Field(min_length=1)
    address: str = Field(min_length=1)
    road_address_name: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    phone: str | None = None
    place_url: str | None = None
    category_name: str | None = None
    selection_type: AccommodationSelectionType
