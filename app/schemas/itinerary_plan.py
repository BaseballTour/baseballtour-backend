from enum import Enum

from pydantic import AwareDatetime, Field

from app.models.itinerary import ExcludedPlace, ItineraryDay
from app.schemas.base import ApiModel


class ItineraryPlanStatus(str, Enum):
    """생성된 일정 계획의 사용 상태."""

    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class ItineraryPlanDocument(ApiModel):
    """Firestore itineraryPlans 문서에 저장되는 필드."""

    trip_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    status: ItineraryPlanStatus = ItineraryPlanStatus.ACTIVE
    algorithm_version: str = Field(min_length=1)
    total_travel_minutes: int = Field(ge=0)
    days: list[ItineraryDay] = Field(default_factory=list)
    excluded_places: list[ExcludedPlace] = Field(
        default_factory=list
    )
    created_at: AwareDatetime
    updated_at: AwareDatetime


class ItineraryPlanRecord(ItineraryPlanDocument):
    """Firestore 문서 ID가 포함된 일정 계획."""

    plan_id: str = Field(min_length=1)
