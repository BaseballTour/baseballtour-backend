from pydantic import AwareDatetime, Field

from app.models.place import Place
from app.schemas.base import ApiModel


class PlayerPickDocument(ApiModel):
    """Firestore에 관리자가 지정하는 선수 추천 장소."""

    stadium_id: str = Field(min_length=1)
    player_name: str = Field(min_length=1)
    place_id: str = Field(pattern=r"^tour_.+$")
    created_at: AwareDatetime


class PlayerPickRecord(PlayerPickDocument):
    player_pick_id: str = Field(min_length=1)


class PlayerPickResponse(ApiModel):
    player_pick_id: str
    stadium_id: str
    player_name: str
    place: Place
