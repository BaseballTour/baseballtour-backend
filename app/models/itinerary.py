from datetime import date, datetime
from enum import Enum

from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_serializer,
    field_validator,
    model_validator,
)

from app.core.time import to_korea_datetime
from app.models.place import PlaceCategory
from app.models.travel_preferences import ScheduleDensity, TravelStyle


def to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


def normalize_short_description(
    value: str | None,
) -> str | None:
    """장소 소개를 한 줄 표시용 문자열로 정규화합니다."""

    normalized = " ".join((value or "").split())

    return normalized or None


class AlgorithmModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
    )

    @field_validator("*", mode="after", check_fields=False)
    @classmethod
    def normalize_datetime_to_korea(cls, value: Any) -> Any:
        if isinstance(value, datetime):
            return to_korea_datetime(value)
        return value

    @field_serializer(
        "game_start_at",
        "trip_start_at",
        "trip_end_at",
        "scheduled_start_at",
        "scheduled_end_at",
        when_used="json",
        check_fields=False,
    )
    def serialize_datetime_as_korea(
        self,
        value: datetime,
    ) -> datetime:
        """일정 알고리즘 datetime을 한국시간으로 변환해 직렬화합니다."""
        return to_korea_datetime(value)


class DayType(str, Enum):
    ARRIVAL_DAY = "ARRIVAL_DAY"
    GAME_DAY = "GAME_DAY"
    NON_GAME_DAY = "NON_GAME_DAY"
    DEPARTURE_DAY = "DEPARTURE_DAY"


class ItineraryItemType(str, Enum):
    ARRIVAL_POINT = "ARRIVAL_POINT"
    DEPARTURE_POINT = "DEPARTURE_POINT"
    ACCOMMODATION = "ACCOMMODATION"
    PLACE = "PLACE"
    STADIUM = "STADIUM"


class TravelMode(str, Enum):
    WALK = "WALK"
    TRANSIT = "TRANSIT"


class TravelTimeSource(str, Enum):
    KAKAO = "KAKAO"
    ODSAY = "ODSAY"
    ESTIMATED = "ESTIMATED"
    FAKE = "FAKE"


class ItineraryItemAddedBy(str, Enum):
    USER = "USER"
    ALGORITHM = "ALGORITHM"


class ExcludedReasonCode(str, Enum):
    INSUFFICIENT_TIME = "INSUFFICIENT_TIME"
    OUTSIDE_BUSINESS_HOURS = "OUTSIDE_BUSINESS_HOURS"
    CLOSED_DAY = "CLOSED_DAY"
    ROUTE_INEFFICIENT = "ROUTE_INEFFICIENT"
    DUPLICATE_PLACE = "DUPLICATE_PLACE"
    INVALID_PLACE = "INVALID_PLACE"
    ADMISSION_DEADLINE = "ADMISSION_DEADLINE"
    ANCHOR_CONFLICT = "ANCHOR_CONFLICT"


class GeoPoint(AlgorithmModel):
    place_id: str | None = None
    name: str
    address: str = ""
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class GameAnchor(GeoPoint):
    game_id: str
    stadium_id: str
    game_start_at: datetime
    required_arrival_minutes: int = Field(default=40, ge=0)


class SelectedPlaceInput(AlgorithmModel):
    place_id: str
    is_required: bool = False


class TripInput(AlgorithmModel):
    trip_id: str
    trip_start_at: datetime
    trip_end_at: datetime
    arrival_point: GeoPoint
    departure_point: GeoPoint
    accommodation: GeoPoint | None = None
    game_anchor: GameAnchor
    selected_places: list[SelectedPlaceInput] = Field(
        default_factory=list
    )
    auto_fill_recommendations: bool = True
    travel_style: TravelStyle = TravelStyle.BALANCED
    schedule_density: ScheduleDensity = ScheduleDensity.MODERATE

    @model_validator(mode="after")
    def validate_period_and_timezone(self) -> "TripInput":
        datetimes = [
            self.trip_start_at,
            self.trip_end_at,
            self.game_anchor.game_start_at,
        ]
        if any(value.tzinfo is None for value in datetimes):
            raise ValueError("날짜와 시간에는 timezone 정보가 필요합니다.")
        if self.trip_end_at <= self.trip_start_at:
            raise ValueError("여행 종료 시간은 시작 시간보다 늦어야 합니다.")
        if not self.trip_start_at <= self.game_anchor.game_start_at <= self.trip_end_at:
            raise ValueError("경기 시간은 여행 기간 안에 있어야 합니다.")
        return self


class ExcludedPlace(AlgorithmModel):
    place_id: str
    is_required: bool = False
    reason_code: ExcludedReasonCode
    message: str


class ItineraryItem(AlgorithmModel):
    item_type: ItineraryItemType = Field(
        alias="type",
        serialization_alias="type",
    )
    sequence: int = Field(ge=1)
    place_id: str | None = None
    category: PlaceCategory | None = Field(
        default=None,
        description="PLACE 항목의 내부 장소 카테고리",
    )
    thumbnail_url: str | None = Field(
        default=None,
        description="장소 카드에 표시할 대표 이미지",
    )
    short_description: str | None = Field(
        default=None,
        description="PLACE 항목의 한 줄 표시용 장소 소개",
    )
    overview: str | None = Field(
        default=None,
        description="장소 한 줄 소개 또는 원문 소개",
    )
    name: str
    address: str = Field(min_length=1)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    scheduled_start_at: datetime
    scheduled_end_at: datetime
    travel_minutes_from_previous: int = Field(default=0, ge=0)
    travel_distance_meters_from_previous: int = Field(default=0, ge=0)
    transfer_buffer_minutes: int = Field(
        default=0,
        ge=0,
        description="이동시간과 별도로 확보한 환승·대기 여유시간",
    )
    travel_mode: TravelMode | None = None
    travel_time_source: TravelTimeSource | None = None
    is_required: bool = False
    added_by: ItineraryItemAddedBy | None = None

    @model_validator(mode="after")
    def validate_schedule(self) -> "ItineraryItem":
        if (
            self.scheduled_start_at.tzinfo is None
            or self.scheduled_end_at.tzinfo is None
        ):
            raise ValueError("일정 시간에는 timezone 정보가 필요합니다.")
        if self.scheduled_end_at <= self.scheduled_start_at:
            raise ValueError("일정 종료 시간은 시작 시간보다 늦어야 합니다.")
        return self


class ItineraryDay(AlgorithmModel):
    date: date
    day_type: DayType
    items: list[ItineraryItem] = Field(default_factory=list)


class RecommendationSummary(AlgorithmModel):
    """자동 추천 후보 준비와 일정 삽입 결과 요약."""

    fetched_count: int = Field(default=0, ge=0)
    candidate_count: int = Field(default=0, ge=0)
    scheduled_count: int = Field(default=0, ge=0)
    category_distribution: dict[str, int] = Field(default_factory=dict)
    filtered_counts: dict[str, int] = Field(default_factory=dict)
    placement_rejected_attempts: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "장소 고유 개수가 아니라 날짜·삽입 위치별 실패 시도 횟수"
        ),
    )


class ItineraryResult(AlgorithmModel):
    trip_id: str
    algorithm_version: str = "draft-v0.1"
    total_travel_minutes: int = Field(default=0, ge=0)
    total_travel_distance_meters: int = Field(default=0, ge=0)
    days: list[ItineraryDay] = Field(default_factory=list)
    excluded_places: list[ExcludedPlace] = Field(default_factory=list)
    auto_fill_applied: bool = False
    auto_recommended_place_count: int = Field(default=0, ge=0)
    recommendation_summary: RecommendationSummary | None = None

    @computed_field
    @property
    def has_required_place_conflict(self) -> bool:
        return any(place.is_required for place in self.excluded_places)

    @model_validator(mode="after")
    def validate_total_travel_minutes(self) -> "ItineraryResult":
        calculated_total = sum(
            item.travel_minutes_from_previous
            for day in self.days
            for item in day.items
        )
        if self.total_travel_minutes != calculated_total:
            raise ValueError(
                "totalTravelMinutes는 모든 일정 항목의 "
                "travelMinutesFromPrevious 합계여야 합니다."
            )
        calculated_distance = sum(
            item.travel_distance_meters_from_previous
            for day in self.days
            for item in day.items
        )
        if self.total_travel_distance_meters != calculated_distance:
            raise ValueError(
                "totalTravelDistanceMeters는 모든 일정 항목의 "
                "travelDistanceMetersFromPrevious 합계여야 합니다."
            )
        return self
