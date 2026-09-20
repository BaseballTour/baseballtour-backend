from enum import Enum

from pydantic import AwareDatetime, Field

from app.models.place import Place, PlaceCategory
from app.schemas.base import ApiModel


class PlayerPosition(str, Enum):
    PITCHER = "PITCHER"
    CATCHER = "CATCHER"
    INFIELDER = "INFIELDER"
    OUTFIELDER = "OUTFIELDER"
    COACH = "COACH"
    STAFF = "STAFF"
    TEAM_GROUP = "TEAM_GROUP"


class RecommendationEvidenceStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    DISPUTED = "DISPUTED"


class PlayerPickDocument(ApiModel):
    """독립적으로 큐레이션하고 Kakao에는 ID로만 연결하는 추천 장소."""

    stadium_id: str = Field(min_length=1)
    player_name: str = Field(min_length=1)
    player_position: PlayerPosition | None = Field(
        default=None,
        description="선수 포지션 또는 추천 주체 역할. 해당 없음은 null",
    )
    place_name: str = Field(
        min_length=1,
        description="관리자가 독립적으로 확인해 입력한 장소명",
    )
    address: str = Field(
        default="",
        description="관리자가 독립적인 출처로 확인한 주소",
    )
    category: PlaceCategory = Field(
        default=PlaceCategory.RESTAURANT,
        description="서비스가 직접 분류한 내부 카테고리",
    )
    kakao_place_id: str | None = Field(
        default=None,
        description="실시간 Kakao Local 조회 결과를 식별할 연결 ID",
    )
    recommendation_note: str | None = Field(
        default=None,
        description="부모님 운영·선수단 공통 추천 등 관리자 설명",
    )
    recommendation_evidence_status: RecommendationEvidenceStatus = Field(
        default=RecommendationEvidenceStatus.UNVERIFIED,
        description="선수 추천 근거의 확인 상태",
    )
    recommendation_source_url: str | None = Field(
        default=None,
        pattern=r"^https?://",
        description="선수가 해당 장소를 언급한 영상·기사·게시물 URL",
    )
    recommendation_source_title: str | None = Field(
        default=None,
        description="추천 출처의 영상·기사·게시물 제목",
    )
    recommendation_source_publisher: str | None = Field(
        default=None,
        description="추천 출처를 게시한 구단·방송사·채널명",
    )
    recommendation_verified_at: AwareDatetime | None = Field(
        default=None,
        description="추천 출처를 마지막으로 확인한 시각",
    )
    created_at: AwareDatetime
    updated_at: AwareDatetime | None = None


class PlayerPickRecord(PlayerPickDocument):
    player_pick_id: str = Field(min_length=1)


class PlayerPickResponse(ApiModel):
    player_pick_id: str
    stadium_id: str
    player_name: str
    player_position: PlayerPosition | None = None
    place: Place
    recommendation_note: str | None = None
    recommendation_evidence_status: RecommendationEvidenceStatus = (
        RecommendationEvidenceStatus.UNVERIFIED
    )
    recommendation_source_url: str | None = Field(
        default=None,
        description="선수가 해당 장소를 언급한 영상·기사·게시물 URL",
    )
    recommendation_source_title: str | None = None
    recommendation_source_publisher: str | None = None
    recommendation_verified_at: AwareDatetime | None = None
