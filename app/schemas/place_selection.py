from datetime import datetime

from pydantic import ConfigDict, Field

from app.schemas.base import ApiModel


class PlaceSelectionCreateRequest(ApiModel):
    """여행에 장소를 선택하는 요청."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "placeId": "tour_123456",
                    "isRequired": True,
                }
            ]
        }
    )

    place_id: str = Field(
        min_length=1,
        description="선택할 서비스 내부 장소 ID",
    )
    is_required: bool = Field(
        default=False,
        description="일정에 반드시 포함해야 하는 장소인지 여부",
    )


class PlaceSelectionDocument(ApiModel):
    """Firestore placeSelections 문서."""

    place_id: str = Field(
        min_length=1,
        description="선택한 서비스 내부 장소 ID",
    )
    is_required: bool = False
    created_at: datetime


class PlaceSelectionRecord(PlaceSelectionDocument):
    """Firestore에서 조회한 장소 선택 정보."""

    pass


class PlaceSelectionResponse(ApiModel):
    """장소 선택 API 응답."""

    place_id: str
    is_required: bool
    created_at: datetime
