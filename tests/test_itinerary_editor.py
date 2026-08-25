from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.algorithms.itinerary_editor import (
    ItineraryEditError,
    insert_place_item,
    recalculate_day_schedule,
    recalculate_day_travel_only,
    remove_place_item,
    reorder_place_items,
    update_place_item_fixed,
    update_place_item_start,
)
from app.algorithms.travel_time import TravelTimeMatrix
from app.models.itinerary import (
    DayType,
    ItineraryItemType,
    TravelTimeSource,
)
from app.schemas.itinerary_plan import (
    ItineraryPlanDay,
    ItineraryPlanItem,
)


TZ = ZoneInfo("Asia/Seoul")


def make_item(
    *,
    item_id: str,
    item_type: ItineraryItemType,
    sequence: int,
    place_id: str | None,
    start_hour: int,
    start_minute: int = 0,
    duration_minutes: int = 60,
    is_fixed: bool = False,
) -> ItineraryPlanItem:
    start = datetime(
        2026,
        8,
        15,
        start_hour,
        start_minute,
        tzinfo=TZ,
    )

    from datetime import timedelta

    return ItineraryPlanItem(
        item_id=item_id,
        type=item_type,
        sequence=sequence,
        place_id=place_id,
        name=item_id,
        address="test address",
        latitude=35.0,
        longitude=129.0,
        scheduled_start_at=start,
        scheduled_end_at=(
            start
            + timedelta(
                minutes=duration_minutes
            )
        ),
        travel_minutes_from_previous=0,
        travel_time_source=None,
        is_required=True,
        is_fixed=is_fixed,
    )


def test_reorder_place_items_preserves_anchors() -> None:
    arrival = make_item(
        item_id="arrival",
        item_type=ItineraryItemType.ARRIVAL_POINT,
        sequence=1,
        place_id=None,
        start_hour=9,
        duration_minutes=20,
    )
    first = make_item(
        item_id="item_a",
        item_type=ItineraryItemType.PLACE,
        sequence=2,
        place_id="tour_a",
        start_hour=10,
    )
    second = make_item(
        item_id="item_b",
        item_type=ItineraryItemType.PLACE,
        sequence=3,
        place_id="tour_b",
        start_hour=12,
    )
    accommodation = make_item(
        item_id="hotel",
        item_type=ItineraryItemType.ACCOMMODATION,
        sequence=4,
        place_id=None,
        start_hour=21,
        duration_minutes=20,
    )

    day = ItineraryPlanDay(
        date=date(2026, 8, 15),
        day_type=DayType.ARRIVAL_DAY,
        items=[
            arrival,
            first,
            second,
            accommodation,
        ],
    )

    result = reorder_place_items(
        day,
        [
            "item_b",
            "item_a",
        ],
    )

    assert [
        item.item_id
        for item in result.items
    ] == [
        "arrival",
        "item_b",
        "item_a",
        "hotel",
    ]


def test_reorder_place_items_requires_all_places() -> None:
    day = ItineraryPlanDay(
        date=date(2026, 8, 15),
        day_type=DayType.NON_GAME_DAY,
        items=[
            make_item(
                item_id="item_a",
                item_type=ItineraryItemType.PLACE,
                sequence=1,
                place_id="tour_a",
                start_hour=10,
            ),
            make_item(
                item_id="item_b",
                item_type=ItineraryItemType.PLACE,
                sequence=2,
                place_id="tour_b",
                start_hour=12,
            ),
        ],
    )

    with pytest.raises(ItineraryEditError):
        reorder_place_items(
            day,
            ["item_a"],
        )


def test_fixed_place_cannot_be_reordered_or_deleted() -> None:
    fixed = make_item(
        item_id="fixed",
        item_type=ItineraryItemType.PLACE,
        sequence=1,
        place_id="tour_fixed",
        start_hour=10,
        is_fixed=True,
    )
    other = make_item(
        item_id="other",
        item_type=ItineraryItemType.PLACE,
        sequence=2,
        place_id="tour_other",
        start_hour=12,
    )
    day = ItineraryPlanDay(
        date=date(2026, 8, 15),
        day_type=DayType.NON_GAME_DAY,
        items=[fixed, other],
    )

    with pytest.raises(ItineraryEditError):
        reorder_place_items(day, ["other", "fixed"])
    with pytest.raises(ItineraryEditError):
        remove_place_item(day, "fixed")


def test_update_start_time_preserves_duration_and_fixes_item() -> None:
    item = make_item(
        item_id="place",
        item_type=ItineraryItemType.PLACE,
        sequence=1,
        place_id="tour_place",
        start_hour=10,
        duration_minutes=90,
    )
    day = ItineraryPlanDay(
        date=date(2026, 8, 15),
        day_type=DayType.NON_GAME_DAY,
        items=[item],
    )

    changed = update_place_item_start(
        day,
        "place",
        datetime(2026, 8, 15, 14, 0, tzinfo=TZ),
    )

    assert changed.items[0].scheduled_start_at.hour == 14
    assert changed.items[0].scheduled_end_at.hour == 15
    assert changed.items[0].scheduled_end_at.minute == 30
    assert changed.items[0].is_fixed is True
    unfixed = update_place_item_fixed(changed, "place", False)
    assert unfixed.items[0].is_fixed is False


def test_recalculate_day_schedule_updates_order_and_times() -> None:
    day = ItineraryPlanDay(
        date=date(2026, 8, 15),
        day_type=DayType.NON_GAME_DAY,
        items=[
            make_item(
                item_id="item_b",
                item_type=ItineraryItemType.PLACE,
                sequence=2,
                place_id="tour_b",
                start_hour=12,
            ),
            make_item(
                item_id="item_a",
                item_type=ItineraryItemType.PLACE,
                sequence=1,
                place_id="tour_a",
                start_hour=10,
            ),
        ],
    )

    matrix = TravelTimeMatrix(
        minutes={
            ("arrival", "tour_b"): 15,
            ("tour_b", "tour_a"): 25,
        },
        sources={
            ("arrival", "tour_b"): TravelTimeSource.ODSAY,
            ("tour_b", "tour_a"): TravelTimeSource.ESTIMATED,
        },
    )

    result = recalculate_day_schedule(
        day,
        matrix=matrix,
        start_node_id="arrival",
        day_start_at=datetime(
            2026,
            8,
            15,
            9,
            0,
            tzinfo=TZ,
        ),
    )

    first, second = result.items

    assert first.sequence == 1
    assert first.scheduled_start_at.hour == 9
    assert first.scheduled_start_at.minute == 15
    assert first.travel_minutes_from_previous == 15
    assert first.travel_time_source == TravelTimeSource.ODSAY

    assert second.sequence == 2
    assert second.scheduled_start_at.hour == 10
    assert second.scheduled_start_at.minute == 40
    assert second.travel_minutes_from_previous == 25
    assert second.travel_time_source == TravelTimeSource.ESTIMATED


def test_recalculate_rejects_late_stadium_arrival() -> None:
    place = make_item(
        item_id="item_a",
        item_type=ItineraryItemType.PLACE,
        sequence=1,
        place_id="tour_a",
        start_hour=15,
        duration_minutes=120,
    )

    stadium = make_item(
        item_id="stadium",
        item_type=ItineraryItemType.STADIUM,
        sequence=2,
        place_id="stadium_001",
        start_hour=17,
        duration_minutes=220,
    )

    day = ItineraryPlanDay(
        date=date(2026, 8, 15),
        day_type=DayType.GAME_DAY,
        items=[
            place,
            stadium,
        ],
    )

    matrix = TravelTimeMatrix(
        minutes={
            ("arrival", "tour_a"): 30,
            ("tour_a", "stadium"): 40,
        },
    )

    with pytest.raises(
        ItineraryEditError,
        match="제시간",
    ):
        recalculate_day_schedule(
            day,
            matrix=matrix,
            start_node_id="arrival",
            day_start_at=datetime(
                2026,
                8,
                15,
                15,
                0,
                tzinfo=TZ,
            ),
        )


def test_travel_only_recalculation_keeps_impossible_manual_times() -> None:
    place = make_item(
        item_id="place",
        item_type=ItineraryItemType.PLACE,
        sequence=1,
        place_id="tour_a",
        start_hour=18,
    )
    stadium = make_item(
        item_id="stadium",
        item_type=ItineraryItemType.STADIUM,
        sequence=2,
        place_id="stadium_001",
        start_hour=17,
    )
    day = ItineraryPlanDay(
        date=date(2026, 8, 15),
        day_type=DayType.GAME_DAY,
        items=[place, stadium],
    )
    matrix = TravelTimeMatrix(
        minutes={
            ("arrival", "tour_a"): 30,
            ("tour_a", "stadium"): 40,
        },
    )

    result = recalculate_day_travel_only(
        day,
        matrix=matrix,
        start_node_id="arrival",
    )

    assert result.items[0].scheduled_start_at.hour == 18
    assert result.items[1].scheduled_start_at.hour == 17
    assert result.items[1].travel_minutes_from_previous == 40


def test_remove_place_item_removes_only_target() -> None:
    first = make_item(
        item_id="item_a",
        item_type=ItineraryItemType.PLACE,
        sequence=1,
        place_id="tour_a",
        start_hour=10,
    )

    second = make_item(
        item_id="item_b",
        item_type=ItineraryItemType.PLACE,
        sequence=2,
        place_id="tour_b",
        start_hour=12,
    )

    day = ItineraryPlanDay(
        date=date(2026, 8, 15),
        day_type=DayType.NON_GAME_DAY,
        items=[
            first,
            second,
        ],
    )

    result = remove_place_item(
        day,
        "item_a",
    )

    assert [
        item.item_id
        for item in result.items
    ] == [
        "item_b",
    ]


def test_remove_place_item_rejects_anchor() -> None:
    arrival = make_item(
        item_id="arrival",
        item_type=ItineraryItemType.ARRIVAL_POINT,
        sequence=1,
        place_id=None,
        start_hour=9,
        duration_minutes=20,
    )

    day = ItineraryPlanDay(
        date=date(2026, 8, 15),
        day_type=DayType.ARRIVAL_DAY,
        items=[
            arrival,
        ],
    )

    with pytest.raises(
        ItineraryEditError,
        match="PLACE",
    ):
        remove_place_item(
            day,
            "arrival",
        )


def test_remove_place_item_rejects_unknown_item() -> None:
    day = ItineraryPlanDay(
        date=date(2026, 8, 15),
        day_type=DayType.NON_GAME_DAY,
        items=[],
    )

    with pytest.raises(
        ItineraryEditError,
        match="찾을 수 없습니다",
    ):
        remove_place_item(
            day,
            "unknown_item",
        )


def test_insert_place_item_before_final_anchor() -> None:
    first = make_item(
        item_id="item_a",
        item_type=ItineraryItemType.PLACE,
        sequence=1,
        place_id="tour_a",
        start_hour=10,
    )

    stadium = make_item(
        item_id="stadium",
        item_type=ItineraryItemType.STADIUM,
        sequence=2,
        place_id="stadium_001",
        start_hour=18,
        duration_minutes=220,
    )

    new_item = make_item(
        item_id="item_new",
        item_type=ItineraryItemType.PLACE,
        sequence=99,
        place_id="tour_new",
        start_hour=12,
    )

    day = ItineraryPlanDay(
        date=date(2026, 8, 15),
        day_type=DayType.GAME_DAY,
        items=[
            first,
            stadium,
        ],
    )

    result = insert_place_item(
        day,
        new_item,
    )

    assert [
        item.item_id
        for item in result.items
    ] == [
        "item_a",
        "item_new",
        "stadium",
    ]


def test_insert_place_item_rejects_duplicate_place() -> None:
    current = make_item(
        item_id="item_a",
        item_type=ItineraryItemType.PLACE,
        sequence=1,
        place_id="tour_a",
        start_hour=10,
    )

    duplicate = make_item(
        item_id="item_new",
        item_type=ItineraryItemType.PLACE,
        sequence=2,
        place_id="tour_a",
        start_hour=12,
    )

    day = ItineraryPlanDay(
        date=date(2026, 8, 15),
        day_type=DayType.NON_GAME_DAY,
        items=[
            current,
        ],
    )

    with pytest.raises(
        ItineraryEditError,
        match="이미 일정",
    ):
        insert_place_item(
            day,
            duplicate,
        )


def test_insert_place_item_rejects_anchor() -> None:
    day = ItineraryPlanDay(
        date=date(2026, 8, 15),
        day_type=DayType.NON_GAME_DAY,
        items=[],
    )

    anchor = make_item(
        item_id="hotel",
        item_type=ItineraryItemType.ACCOMMODATION,
        sequence=1,
        place_id=None,
        start_hour=21,
        duration_minutes=20,
    )

    with pytest.raises(
        ItineraryEditError,
        match="PLACE",
    ):
        insert_place_item(
            day,
            anchor,
        )
