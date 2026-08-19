from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PlaceCategory(str, Enum):
    TOURIST_SPOT = "TOURIST_SPOT"
    RESTAURANT = "RESTAURANT"
    CAFE = "CAFE"
    ACCOMMODATION = "ACCOMMODATION"
    CULTURAL_FACILITY = "CULTURAL_FACILITY"
    SHOPPING = "SHOPPING"
    FESTIVAL = "FESTIVAL"
    ACTIVITY = "ACTIVITY"
    OTHER = "OTHER"


CATEGORY_DEFAULT_STAY_MINUTES = {
    PlaceCategory.CAFE: 45,
    PlaceCategory.RESTAURANT: 60,
    PlaceCategory.TOURIST_SPOT: 90,
    PlaceCategory.CULTURAL_FACILITY: 90,
    PlaceCategory.SHOPPING: 60,
    PlaceCategory.ACTIVITY: 120,
    PlaceCategory.FESTIVAL: 120,
    PlaceCategory.OTHER: 60,
    PlaceCategory.ACCOMMODATION: 30,
}


def default_stay_minutes_for(category: PlaceCategory) -> int:
    return CATEGORY_DEFAULT_STAY_MINUTES[category]


class PlaceSource(str, Enum):
    TOUR_API = "TOUR_API"
    KAKAO = "KAKAO"
    LOCAL_DATA = "LOCAL_DATA"
    USER_PICK = "USER_PICK"


class BusinessRuleStatus(str, Enum):
    PARSED = "PARSED"
    MISSING = "MISSING"
    UNPARSABLE = "UNPARSABLE"
    COMPLEX = "COMPLEX"


class Weekday(str, Enum):
    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"


class BusinessHoursRule(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda value: value.split("_")[0] + "".join(
            part.capitalize() for part in value.split("_")[1:]
        ),
        populate_by_name=True,
        serialize_by_alias=True,
        use_enum_values=True,
    )
    weekdays: list[Weekday]
    open_time: str
    close_time: str


class Place(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda value: value.split("_")[0] + "".join(
            part.capitalize() for part in value.split("_")[1:]
        ),
        populate_by_name=True,
        serialize_by_alias=True,
        use_enum_values=True,
        json_schema_extra={
            "examples": [
                {
                    "placeId": "tour_1603175",
                    "name": "관광지 예시",
                    "category": "TOURIST_SPOT",
                    "latitude": 37.5122,
                    "longitude": 127.0719,
                    "address": "서울특별시 송파구",
                    "postalCode": None,
                    "telephone": None,
                    "thumbnailUrl": "https://example.com/place.jpg",
                    "overview": "TourAPI에서 조회한 장소 소개 예시입니다.",
                    "openTime": "10:00",
                    "closeTime": "20:00",
                    "closedDaysText": None,
                    "defaultStayMinutes": 60,
                    "distanceMeters": 850.0,
                    "source": "TOUR_API",
                    "sourceContentId": "1603175",
                    "contentTypeId": "12",
                    "areaCode": "1",
                    "sigunguCode": "18",
                    "categoryCode1": None,
                    "categoryCode2": None,
                    "categoryCode3": None,
                }
            ]
        },
    )

    place_id: str = Field(
        description="서비스 내부에서 사용하는 장소 ID"
    )

    name: str = Field(
        min_length=1,
        description="장소 이름"
    )

    category: PlaceCategory = Field(
        default=PlaceCategory.OTHER,
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
        description="대표 이미지 URL"
    )

    overview: str | None = Field(
        default=None,
        description="장소 소개"
    )

    open_time: str | None = Field(
        default=None,
        description="영업 시작시간 HH:MM"
    )

    close_time: str | None = Field(
        default=None,
        description="영업 종료시간 HH:MM"
    )

    business_hours_status: BusinessRuleStatus = BusinessRuleStatus.MISSING
    business_hours_text: str | None = None
    business_hours_rules: list[BusinessHoursRule] = Field(default_factory=list)

    admission_deadline_time: str | None = Field(
        default=None,
        description="안전하게 해석된 최종 입장 가능 시각 HH:MM",
    )
    admission_deadline_status: BusinessRuleStatus = BusinessRuleStatus.MISSING
    admission_deadline_text: str | None = Field(
        default=None,
        description="입장 마감 관련 TourAPI 원문",
    )

    closed_days_text: str | None = Field(
        default=None,
        description="휴무일 원문"
    )

    closed_days_status: BusinessRuleStatus = BusinessRuleStatus.MISSING
    closed_weekdays: list[Weekday] = Field(default_factory=list)

    default_stay_minutes: int = Field(
        default=60,
        ge=1,
        description="기본 예상 체류시간"
    )

    distance_meters: float | None = Field(
        default=None,
        ge=0,
        description="기준 지점으로부터의 거리, 미터 단위"
    )

    source: PlaceSource = Field(
        default=PlaceSource.TOUR_API,
        description="장소 데이터 출처"
    )

    source_content_id: str | None = Field(
        default=None,
        description="외부 API의 원본 콘텐츠 ID"
    )

    kakao_place_id: str | None = Field(
        default=None,
        description="정보 보충에 사용된 카카오 장소 ID"
    )

    enriched_by: list[PlaceSource] = Field(
        default_factory=list,
        description="기본 출처 외에 장소 정보를 보충한 데이터 출처"
    )

    content_type_id: str | None = Field(
        default=None,
        description="TourAPI 콘텐츠 유형 ID"
    )

    lcls_system1: str | None = Field(
        default=None,
        description="TourAPI 신분류 대분류 코드"
    )

    lcls_system2: str | None = Field(
        default=None,
        description="TourAPI 신분류 중분류 코드"
    )

    lcls_system3: str | None = Field(
        default=None,
        description="TourAPI 신분류 소분류 코드"
    )

    @model_validator(mode="after")
    def validate_source_content_id(self) -> "Place":
        if (
            self.source in {PlaceSource.TOUR_API, PlaceSource.KAKAO}
            and not self.source_content_id
        ):
            raise ValueError(
                "TOUR_API 또는 KAKAO 장소에는 "
                "sourceContentId가 필요합니다."
            )
        return self

