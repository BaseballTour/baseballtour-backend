from app.models.itinerary import ItineraryItemType
from app.schemas.trip_share import (
    SharedAccommodation,
    SharedAccommodationItem,
    SharedItineraryDay,
    SharedItineraryItem,
    SharedItineraryPlan,
    SharedTripResponse,
)
from app.schemas.game import GameResponse


PUBLIC_ITEM_FIELDS = {
    "item_type",
    "sequence",
    "place_id",
    "place_url",
    "category",
    "thumbnail_url",
    "short_description",
    "overview",
    "is_player_pick",
    "recommended_by_players",
    "recommendation_note",
    "name",
    "address",
    "latitude",
    "longitude",
    "scheduled_start_at",
    "scheduled_end_at",
    "travel_minutes_from_previous",
    "travel_distance_meters_from_previous",
    "transfer_buffer_minutes",
    "travel_mode",
    "travel_time_source",
    "is_required",
}


def to_shared_plan(plan) -> SharedItineraryPlan:
    days = []

    for day in plan.days:
        items = []
        for item in day.items:
            if item.item_type == ItineraryItemType.ACCOMMODATION:
                items.append(
                    SharedAccommodationItem(
                        item_type=ItineraryItemType.ACCOMMODATION,
                        sequence=item.sequence,
                        name=item.name,
                    )
                )
            else:
                data = item.model_dump(
                    include=PUBLIC_ITEM_FIELDS,
                    by_alias=False,
                )
                items.append(SharedItineraryItem.model_validate(data))

        days.append(
            SharedItineraryDay(
                date=day.date,
                day_type=day.day_type,
                items=items,
            )
        )

    return SharedItineraryPlan(
        total_travel_minutes=plan.total_travel_minutes,
        total_travel_distance_meters=plan.total_travel_distance_meters,
        days=days,
    )


def to_shared_trip(
    *,
    trip,
    plan,
    game: GameResponse,
    subtitle: str,
) -> SharedTripResponse:
    accommodation = (
        SharedAccommodation(name=trip.accommodation.name)
        if trip.accommodation is not None
        else None
    )

    return SharedTripResponse(
        title=trip.title,
        subtitle=subtitle,
        trip_start_at=trip.trip_start_at,
        trip_end_at=trip.trip_end_at,
        game=game,
        accommodation=accommodation,
        plan=to_shared_plan(plan),
    )


def resolve_shared_subtitle(trip) -> str:
    """공유 여행 부제목이 없으면 한국시간 여행 날짜를 사용합니다."""
    if trip.subtitle:
        return trip.subtitle

    from app.core.time import to_korea_datetime

    start_date = to_korea_datetime(trip.trip_start_at).date()
    end_date = to_korea_datetime(trip.trip_end_at).date()

    start_text = start_date.strftime("%Y.%m.%d")
    if start_date == end_date:
        return start_text

    return f"{start_text} ~ {end_date.strftime('%Y.%m.%d')}"
