from pydantic import AwareDatetime, Field

from app.schemas.base import ApiModel


class StadiumDocument(ApiModel):
    """Firestore stadiums 문서에 저장되는 필드."""

    name: str = Field(
        min_length=1,
        description="구장 이름",
    )
    address: str = Field(
        min_length=1,
        description="구장 주소",
    )
    latitude: float = Field(
        ge=-90,
        le=90,
        description="구장 위도",
    )
    longitude: float = Field(
        ge=-180,
        le=180,
        description="구장 경도",
    )
    region: str = Field(
        min_length=1,
        description="구장 지역",
    )
    created_at: AwareDatetime
    updated_at: AwareDatetime


class StadiumResponse(StadiumDocument):
    """구장 API 응답 모델."""

    stadium_id: str


class StadiumSummaryResponse(ApiModel):
    """경기 응답에 포함되는 구장 요약 정보."""

    stadium_id: str
    name: str
    address: str
    latitude: float
    longitude: float
