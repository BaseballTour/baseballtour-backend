from datetime import date
from enum import Enum

from pydantic import (
    AwareDatetime,
    ConfigDict,
    Field,
    field_validator,
)

from app.models.itinerary import (
    ExcludedPlace,
    ItineraryDay,
    ItineraryItem,
    RecommendationSummary,
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
    recommendation_summary: RecommendationSummary | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class ItineraryPlanRecord(ItineraryPlanDocument):
    """Firestore 문서 ID가 포함된 일정 계획."""

    plan_id: str = Field(min_length=1)


class ItineraryPlanResponse(ApiModel):
    """일정 생성 및 상세 조회 API 응답."""

    plan_id: str = Field(min_length=1)
    trip_id: str = Field(min_length=1)
    status: ItineraryPlanStatus
    algorithm_version: str = Field(min_length=1)
    total_travel_minutes: int = Field(ge=0)
    days: list[ItineraryPlanDay] = Field(default_factory=list)
    excluded_places: list[ExcludedPlace] = Field(
        default_factory=list
    )
    recommendation_summary: RecommendationSummary | None = None


class ItineraryPlanReorderRequest(ApiModel):
    """특정 날짜의 PLACE 항목 순서 변경 요청."""

    date: date
    item_ids: list[str] = Field(min_length=1)

    @field_validator("item_ids")
    @classmethod
    def validate_item_ids(
        cls,
        value: list[str],
    ) -> list[str]:
        if any(not item_id.strip() for item_id in value):
            raise ValueError(
                "itemIds에는 빈 itemId를 사용할 수 없습니다."
            )

        if len(value) != len(set(value)):
            raise ValueError(
                "itemIds에는 중복된 itemId를 사용할 수 없습니다."
            )

        return value


class ItineraryPlanAddItemRequest(ApiModel):
    """특정 날짜에 장소를 추가하는 요청."""

    date: date
    place_id: str = Field(min_length=1)
    is_required: bool = True
    scheduled_start_at: AwareDatetime | None = Field(
        default=None,
        description=(
            "사용자 지정 시작시각. 생략하면 직전 항목과 "
            "이동시간을 기준으로 정합니다."
        ),
    )


class ItineraryPlanFixedRequest(ApiModel):
    """일정 PLACE 항목의 고정 여부 변경 요청."""

    is_fixed: bool


class ItineraryPlanTimeUpdateRequest(ApiModel):
    """일정 PLACE 항목의 시작시간 변경 요청."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "scheduledStartAt": (
                        "2026-08-19T10:00:00+09:00"
                    )
                }
            ]
        }
    )

    scheduled_start_at: AwareDatetime
