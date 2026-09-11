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
