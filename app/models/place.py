from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class PlaceCategory(str, Enum):
    TOURIST_SPOT = "TOURIST_SPOT"
    CULTURE = "CULTURE"
    FESTIVAL = "FESTIVAL"
    ACTIVITY = "ACTIVITY"
    ACCOMMODATION = "ACCOMMODATION"
    SHOPPING = "SHOPPING"
    RESTAURANT = "RESTAURANT"
    UNKNOWN = "UNKNOWN"


class PlaceSource(str, Enum):
    TOUR_API = "TOUR_API"
    LOCAL_DATA = "LOCAL_DATA"
    USER_PICK = "USER_PICK"


class Place(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        use_enum_values=True,
    )

    id: str = Field(
        description="서비스 내부에서 사용하는 장소 ID"
    )

    name: str = Field(
        min_length=1,
        description="장소 이름"
    )

    category: PlaceCategory = Field(
        default=PlaceCategory.UNKNOWN,
        description="서비스 내부 장소 카테고리"
    )

    latitude: float = Field(
        ge=-90,
        le=90,
        description="위도"
    )

    longitude: float = Field(
        ge=-180,
        le=180,
        description="경도"
    )

    address: str = Field(
        default="",
        description="전체 주소"
    )

    postal_code: str | None = Field(
        default=None,
        alias="postalCode",
        description="우편번호"
    )

    telephone: str | None = Field(
        default=None,
        description="전화번호"
    )

    thumbnail_url: str | None = Field(
        default=None,
        alias="thumbnailUrl",
        description="대표 이미지 URL"
    )

    distance_meters: float | None = Field(
        default=None,
        alias="distanceMeters",
        ge=0,
        description="기준 지점으로부터의 거리, 미터 단위"
    )

    source: PlaceSource = Field(
        default=PlaceSource.TOUR_API,
        description="장소 데이터 출처"
    )

    source_content_id: str | None = Field(
        default=None,
        alias="sourceContentId",
        description="외부 API의 원본 콘텐츠 ID"
    )

    content_type_id: str | None = Field(
        default=None,
        alias="contentTypeId",
        description="TourAPI 콘텐츠 유형 ID"
    )

    area_code: str | None = Field(
        default=None,
        alias="areaCode",
        description="TourAPI 지역 코드"
    )

    sigungu_code: str | None = Field(
        default=None,
        alias="sigunguCode",
        description="TourAPI 시군구 코드"
    )

    category_code1: str | None = Field(
        default=None,
        alias="categoryCode1",
        description="TourAPI 대분류 코드 cat1"
    )

    category_code2: str | None = Field(
        default=None,
        alias="categoryCode2",
        description="TourAPI 중분류 코드 cat2"
    )

    category_code3: str | None = Field(
        default=None,
        alias="categoryCode3",
        description="TourAPI 소분류 코드 cat3"
    )

