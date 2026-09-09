from datetime import date as Date
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field

from app.models.itinerary import (
    DayType,
    ItineraryItemType,
    TravelMode,
    TravelTimeSource,
)
from app.models.place import PlaceCategory
from app.schemas.base import ApiModel
from app.schemas.game import GameResponse


class TripShareResponse(ApiModel):
    share_token: str
    share_url: str | None = None


class TripShareRevokeResponse(ApiModel):
    revoked: bool


class SharedAccommodation(ApiModel):
    name: str


class SharedItineraryItem(ApiModel):
    item_type: Literal[
        ItineraryItemType.ARRIVAL_POINT,
        ItineraryItemType.DEPARTURE_POINT,
        ItineraryItemType.PLACE,
        ItineraryItemType.STADIUM,
    ] = Field(alias="type")
    sequence: int
    place_id: str | None = None
    place_url: str | None = None
    category: PlaceCategory | None = None
    thumbnail_url: str | None = None
    short_description: str | None = None
    overview: str | None = None
    is_player_pick: bool = False
    recommended_by_players: list[str] = Field(default_factory=list)
    recommendation_note: str | None = None
    name: str
    address: str
    latitude: float
    longitude: float
    scheduled_start_at: AwareDatetime
    scheduled_end_at: AwareDatetime
    travel_minutes_from_previous: int = 0
    travel_distance_meters_from_previous: int = 0
    transfer_buffer_minutes: int = 0
    travel_mode: TravelMode | None = None
    travel_time_source: TravelTimeSource | None = None
    is_required: bool = False


class SharedAccommodationItem(ApiModel):
    item_type: Literal[ItineraryItemType.ACCOMMODATION] = Field(alias="type")
    sequence: int
    name: str


SharedItem = Annotated[
    SharedItineraryItem | SharedAccommodationItem,
    Field(discriminator="item_type"),
]


class SharedItineraryDay(ApiModel):
    date: Date
    day_type: DayType
    items: list[SharedItem] = Field(default_factory=list)


class SharedItineraryPlan(ApiModel):
    total_travel_minutes: int = 0
    total_travel_distance_meters: int = 0
    days: list[SharedItineraryDay] = Field(default_factory=list)


class SharedTripResponse(ApiModel):
    title: str
    subtitle: str
    trip_start_at: AwareDatetime
    trip_end_at: AwareDatetime
    game: GameResponse
    accommodation: SharedAccommodation | None = None
    plan: SharedItineraryPlan
