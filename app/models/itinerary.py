from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


def to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


class AlgorithmModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
    )


class DayType(str, Enum):
    ARRIVAL_DAY = "ARRIVAL_DAY"
    GAME_DAY = "GAME_DAY"
    FREE_DAY = "FREE_DAY"
    DEPARTURE_DAY = "DEPARTURE_DAY"


class GeoPoint(AlgorithmModel):
    name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class GameAnchor(GeoPoint):
    game_id: str
    game_start_at: datetime
    required_arrival_minutes: int = Field(default=40, ge=0)


class TripInput(AlgorithmModel):
    trip_id: str
    trip_start_at: datetime
    trip_end_at: datetime
    arrival_point: GeoPoint
    departure_point: GeoPoint
    accommodation: GeoPoint | None = None
    game_anchor: GameAnchor
    selected_place_ids: list[str] = Field(default_factory=list)

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
    reason_code: str
    message: str


class ItineraryItem(AlgorithmModel):
    sequence: int = Field(ge=1)
    place_id: str | None = None
    name: str
    scheduled_start_at: datetime
    scheduled_end_at: datetime
    travel_minutes_from_previous: int = Field(default=0, ge=0)
    is_required: bool = False


class ItineraryDay(AlgorithmModel):
    date: date
    day_type: DayType
    items: list[ItineraryItem] = Field(default_factory=list)


class ItineraryResult(AlgorithmModel):
    trip_id: str
    algorithm_version: str = "draft-v0.1"
    total_travel_minutes: int = Field(default=0, ge=0)
    days: list[ItineraryDay] = Field(default_factory=list)
    excluded_places: list[ExcludedPlace] = Field(default_factory=list)
