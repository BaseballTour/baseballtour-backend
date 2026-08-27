from datetime import datetime, time, timedelta

from app.algorithms.itinerary_generator import DEFAULT_DAY_END
from app.algorithms.travel_time import TravelTimeMatrix
from app.models.itinerary import (
    DayType,
    ItineraryItemType,
)
from app.schemas.itinerary_plan import (
    ItineraryPlanDay,
    ItineraryPlanItem,
)


class ItineraryEditError(ValueError):
    """일정 편집 결과를 유효한 시간표로 만들 수 없을 때 발생합니다."""

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.details = details


def _conflict_item(item: ItineraryPlanItem) -> dict[str, object]:
    return {
        "itemId": item.item_id,
        "type": item.item_type.value,
        "placeId": item.place_id,
        "name": item.name,
        "scheduledStartAt": item.scheduled_start_at.isoformat(),
        "scheduledEndAt": item.scheduled_end_at.isoformat(),
    }


def item_node_id(
    item: ItineraryPlanItem,
) -> str:
    """일정 항목을 이동시간 Matrix의 node ID로 변환합니다."""

    if item.item_type == ItineraryItemType.ARRIVAL_POINT:
        return "arrival"

    if item.item_type == ItineraryItemType.DEPARTURE_POINT:
        return "departure"

    if item.item_type == ItineraryItemType.ACCOMMODATION:
        return "accommodation"

    if item.item_type == ItineraryItemType.STADIUM:
        return "stadium"

    if (
        item.item_type == ItineraryItemType.PLACE
        and item.place_id is not None
    ):
        return item.place_id

    raise ItineraryEditError(
        "일정 항목의 이동시간 node ID를 결정할 수 없습니다."
    )


def reorder_place_items(
    day: ItineraryPlanDay,
    item_ids: list[str],
) -> ItineraryPlanDay:
    """
    앵커 위치는 유지하고 PLACE 항목의 순서만 변경합니다.

    요청에는 해당 날짜의 모든 PLACE itemId가 정확히 한 번씩
    포함되어야 합니다.
    """

    place_items = [
        item
        for item in day.items
        if item.item_type == ItineraryItemType.PLACE
    ]

    current_ids = [
        item.item_id
        for item in place_items
    ]

    if len(item_ids) != len(current_ids):
        raise ItineraryEditError(
            "해당 날짜의 모든 PLACE itemId를 전달해야 합니다."
        )

    if set(item_ids) != set(current_ids):
        raise ItineraryEditError(
            "itemIds가 현재 일정의 PLACE 항목과 일치하지 않습니다."
        )

    item_by_id = {
        item.item_id: item
        for item in place_items
    }

    reordered = iter(
        item_by_id[item_id]
        for item_id in item_ids
    )

    new_items = [
        (
            next(reordered)
            if item.item_type == ItineraryItemType.PLACE
            else item
        )
        for item in day.items
    ]

    for index, item in enumerate(day.items):
        if item.is_fixed and new_items[index].item_id != item.item_id:
            raise ItineraryEditError(
                "고정한 장소의 순서는 변경할 수 없습니다.",
                details={
                    "fixedItem": _conflict_item(item),
                    "conflictingItem": _conflict_item(new_items[index]),
                },
            )

    return ItineraryPlanDay(
        date=day.date,
        day_type=day.day_type,
        items=new_items,
    )


def recalculate_day_schedule(
    day: ItineraryPlanDay,
    *,
    matrix: TravelTimeMatrix,
    start_node_id: str,
    day_start_at: datetime,
) -> ItineraryPlanDay:
    """
    현재 항목 순서를 그대로 유지하며 이동시간과 방문시간을 재계산합니다.

    STADIUM/DEPARTURE_POINT는 기존 예약 시간을 고정하고,
    ACCOMMODATION은 일반 날짜에서 21:00보다 이르게 시작하지 않습니다.
    """

    if day_start_at.tzinfo is None:
        raise ItineraryEditError(
            "day_start_at에는 timezone 정보가 필요합니다."
        )

    if not day.items:
        return day

    rebuilt: list[ItineraryPlanItem] = []

    previous_node_id = start_node_id
    cursor = day_start_at

    for sequence, item in enumerate(
        day.items,
        start=1,
    ):
        node_id = item_node_id(item)
        duration = (
            item.scheduled_end_at
            - item.scheduled_start_at
        )

        if item.item_type == ItineraryItemType.ARRIVAL_POINT:
            if rebuilt:
                raise ItineraryEditError(
                    "ARRIVAL_POINT는 날짜의 첫 항목이어야 합니다."
                )

            start = item.scheduled_start_at
            end = item.scheduled_end_at
            travel = 0
            travel_source = None

        elif item.item_type in {
            ItineraryItemType.STADIUM,
            ItineraryItemType.DEPARTURE_POINT,
        } or item.is_fixed:
            travel = matrix.get(
                previous_node_id,
                node_id,
            )
            travel_source = matrix.get_source(
                previous_node_id,
                node_id,
            )

            earliest_arrival = (
                cursor
                + _minutes(travel)
            )

            start = item.scheduled_start_at
            end = item.scheduled_end_at

            if earliest_arrival > start:
                raise ItineraryEditError(
                    "변경한 일정으로는 고정 일정에 "
                    "제시간에 도착할 수 없습니다.",
                    details={
                        "conflictingItem": _conflict_item(item),
                        "previousItem": (
                            _conflict_item(rebuilt[-1]) if rebuilt else None
                        ),
                        "earliestArrivalAt": earliest_arrival.isoformat(),
                    },
                )

        elif item.item_type == ItineraryItemType.ACCOMMODATION:
            travel = matrix.get(
                previous_node_id,
                node_id,
            )
            travel_source = matrix.get_source(
                previous_node_id,
                node_id,
            )

            start = cursor + _minutes(travel)

            if day.day_type != DayType.GAME_DAY:
                timezone = day_start_at.tzinfo
                earliest = datetime.combine(
                    day.date,
                    DEFAULT_DAY_END,
                    timezone,
                )
                start = max(
                    start,
                    earliest,
                )

            end = start + duration

        else:
            travel = matrix.get(
                previous_node_id,
                node_id,
            )
            travel_source = matrix.get_source(
                previous_node_id,
                node_id,
            )

            start = cursor + _minutes(travel)
            end = start + duration

        rebuilt.append(
            ItineraryPlanItem.model_validate(
                {
                    **item.model_dump(by_alias=False),
                    "sequence": sequence,
                    "scheduled_start_at": start,
                    "scheduled_end_at": end,
                    "travel_minutes_from_previous": travel,
                    "travel_time_source": travel_source,
                }
            )
        )

        cursor = end
        previous_node_id = node_id

    _validate_day_end(
        day=day,
        items=rebuilt,
        day_start_at=day_start_at,
    )

    return ItineraryPlanDay(
        date=day.date,
        day_type=day.day_type,
        items=rebuilt,
    )


def _validate_day_end(
    *,
    day: ItineraryPlanDay,
    items: list[ItineraryPlanItem],
    day_start_at: datetime,
) -> None:
    """
    최종 고정 앵커가 없는 일반 일정은 21:00 안에 끝나야 합니다.
    """

    if not items:
        return

    if any(
        item.item_type
        in {
            ItineraryItemType.STADIUM,
            ItineraryItemType.DEPARTURE_POINT,
            ItineraryItemType.ACCOMMODATION,
        }
        for item in items
    ):
        return

    if day.day_type not in {
        DayType.ARRIVAL_DAY,
        DayType.NON_GAME_DAY,
    }:
        return

    timezone = day_start_at.tzinfo
    day_end = datetime.combine(
        day.date,
        time(
            DEFAULT_DAY_END.hour,
            DEFAULT_DAY_END.minute,
        ),
        timezone,
    )

    if items[-1].scheduled_end_at > day_end:
        raise ItineraryEditError(
            "변경한 일정이 하루 이용 가능 시간을 초과합니다."
        )


def recalculate_day_travel_only(
    day: ItineraryPlanDay,
    *,
    matrix: TravelTimeMatrix,
    start_node_id: str,
) -> ItineraryPlanDay:
    """수동 편집 시간을 유지하고 항목 사이 이동정보만 다시 계산합니다."""

    rebuilt: list[ItineraryPlanItem] = []
    previous_node_id = start_node_id
    for sequence, item in enumerate(day.items, start=1):
        node_id = item_node_id(item)
        if sequence == 1 and item.item_type == ItineraryItemType.ARRIVAL_POINT:
            travel = 0
            travel_source = None
        else:
            travel = matrix.get(previous_node_id, node_id)
            travel_source = matrix.get_source(previous_node_id, node_id)
        rebuilt.append(
            item.model_copy(
                update={
                    "sequence": sequence,
                    "travel_minutes_from_previous": travel,
                    "travel_time_source": travel_source,
                }
            )
        )
        previous_node_id = node_id
    return day.model_copy(update={"items": rebuilt})


def _minutes(value: int) -> timedelta:
    return timedelta(minutes=value)


def remove_place_item(
    day: ItineraryPlanDay,
    item_id: str,
) -> ItineraryPlanDay:
    """특정 PLACE 항목을 일정에서 제거합니다."""

    target = next(
        (
            item
            for item in day.items
            if item.item_id == item_id
        ),
        None,
    )

    if target is None:
        raise ItineraryEditError(
            "삭제할 일정 항목을 찾을 수 없습니다."
        )

    if target.item_type != ItineraryItemType.PLACE:
        raise ItineraryEditError(
            "PLACE 항목만 삭제할 수 있습니다."
        )

    if target.is_fixed:
        raise ItineraryEditError(
            "고정한 장소는 고정을 해제한 뒤 삭제할 수 있습니다."
        )

    return ItineraryPlanDay(
        date=day.date,
        day_type=day.day_type,
        items=[
            item
            for item in day.items
            if item.item_id != item_id
        ],
    )


def insert_place_item(
    day: ItineraryPlanDay,
    item: ItineraryPlanItem,
) -> ItineraryPlanDay:
    """
    새 PLACE 항목을 마지막 PLACE 뒤,
    최종 고정 앵커 앞에 삽입합니다.
    """

    if item.item_type != ItineraryItemType.PLACE:
        raise ItineraryEditError(
            "PLACE 항목만 추가할 수 있습니다."
        )

    if any(
        existing.item_id == item.item_id
        for existing in day.items
    ):
        raise ItineraryEditError(
            "동일한 itemId가 이미 존재합니다."
        )

    if (
        item.place_id is not None
        and any(
            existing.item_type == ItineraryItemType.PLACE
            and existing.place_id == item.place_id
            for existing in day.items
        )
    ):
        raise ItineraryEditError(
            "해당 장소가 이미 일정에 포함되어 있습니다."
        )

    insert_index = len(day.items)

    for index, existing in enumerate(day.items):
        if existing.item_type in {
            ItineraryItemType.STADIUM,
            ItineraryItemType.ACCOMMODATION,
            ItineraryItemType.DEPARTURE_POINT,
        }:
            insert_index = index
            break

    items = list(day.items)
    items.insert(
        insert_index,
        item,
    )

    return ItineraryPlanDay(
        date=day.date,
        day_type=day.day_type,
        items=items,
    )


def update_place_item_fixed(
    day: ItineraryPlanDay,
    item_id: str,
    is_fixed: bool,
) -> ItineraryPlanDay:
    """PLACE 항목의 재생성 고정 여부를 변경합니다."""

    found = False
    items: list[ItineraryPlanItem] = []
    for item in day.items:
        if item.item_id != item_id:
            items.append(item)
            continue
        if item.item_type != ItineraryItemType.PLACE:
            raise ItineraryEditError("PLACE 항목만 고정할 수 있습니다.")
        found = True
        items.append(item.model_copy(update={"is_fixed": is_fixed}))

    if not found:
        raise ItineraryEditError("고정 여부를 변경할 항목을 찾을 수 없습니다.")
    return day.model_copy(update={"items": items})


def update_place_item_start(
    day: ItineraryPlanDay,
    item_id: str,
    scheduled_start_at: datetime,
) -> ItineraryPlanDay:
    """PLACE 시작시간을 수정하고 해당 항목을 고정합니다."""

    if scheduled_start_at.tzinfo is None:
        raise ItineraryEditError("수정할 시간에는 timezone 정보가 필요합니다.")
    found = False
    items: list[ItineraryPlanItem] = []
    for item in day.items:
        if item.item_id != item_id:
            items.append(item)
            continue
        if item.item_type != ItineraryItemType.PLACE:
            raise ItineraryEditError("PLACE 항목의 시간만 수정할 수 있습니다.")
        duration = item.scheduled_end_at - item.scheduled_start_at
        found = True
        items.append(
            item.model_copy(
                update={
                    "scheduled_start_at": scheduled_start_at,
                    "scheduled_end_at": scheduled_start_at + duration,
                    "is_fixed": True,
                }
            )
        )

    if not found:
        raise ItineraryEditError("시간을 변경할 항목을 찾을 수 없습니다.")
    return day.model_copy(update={"items": items})
