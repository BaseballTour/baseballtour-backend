from enum import Enum

from pydantic import AwareDatetime, Field

from app.models.itinerary import (
    ExcludedPlace,
    ItineraryDay,
    ItineraryItem,
)
from app.schemas.base import ApiModel


class ItineraryPlanStatus(str, Enum):
    """생성된 일정 계획의 사용 상태."""

    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class ItineraryPlanItem(ItineraryItem):
    """저장 후 개별 수정할 수 있는 일정 항목."""

    item_id: str = Field(min_length=1)
    is_fixed: bool = Field(
        default=False,
        description="재생성 시 현재 날짜와 순서를 유지할지 여부",
    )


class ItineraryPlanDay(ItineraryDay):
    """저장용 itemId가 포함된 날짜별 일정."""

    items: list[ItineraryPlanItem] = Field(default_factory=list)


class ItineraryPlanDocument(ApiModel):
    """Firestore itineraryPlans 문서에 저장되는 필드."""

    trip_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    status: ItineraryPlanStatus = ItineraryPlanStatus.ACTIVE
    algorithm_version: str = Field(min_length=1)
    total_travel_minutes: int = Field(ge=0)
    days: list[ItineraryPlanDay] = Field(default_factory=list)
    excluded_places: list[ExcludedPlace] = Field(
        default_factory=list
    )
    created_at: AwareDatetime
    updated_at: AwareDatetime


class ItineraryPlanRecord(ItineraryPlanDocument):
    """Firestore 문서 ID가 포함된 일정 계획."""

    plan_id: str = Field(min_length=1)
