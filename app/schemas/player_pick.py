from pydantic import AwareDatetime, Field

from app.models.place import Place
from app.schemas.base import ApiModel


class PlayerPickDocument(ApiModel):
    """Firestore에 관리자가 지정하는 선수 추천 장소."""

    stadium_id: str = Field(min_length=1)
    player_name: str = Field(min_length=1)
    place_id: str = Field(pattern=r"^tour_.+$")
    place_snapshot: Place | None = Field(
        default=None,
        description="TourAPI 장애에도 표시할 수 있는 저장 시점 장소 정보",
    )
    created_at: AwareDatetime
    updated_at: AwareDatetime | None = None


class PlayerPickRecord(PlayerPickDocument):
    player_pick_id: str = Field(min_length=1)


class PlayerPickResponse(ApiModel):
    player_pick_id: str
    stadium_id: str
    player_name: str
    place: Place
