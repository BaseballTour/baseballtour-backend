from pydantic import AwareDatetime, Field

from app.schemas.base import ApiModel


class FavoriteCollectionDocument(ApiModel):
    """사용자별 찜 컬렉션 문서."""

    name: str = Field(min_length=1)
    team_id: str | None = None
    stadium_ids: list[str] = Field(default_factory=list)
    region_codes: list[str] = Field(default_factory=list)
    created_at: AwareDatetime
    updated_at: AwareDatetime


class FavoriteCollectionRecord(FavoriteCollectionDocument):
    collection_id: str = Field(min_length=1)


class FavoriteCollectionItemDocument(ApiModel):
    """장소 원본을 복제하지 않고 places 문서 ID만 참조한다."""

    place_id: str = Field(min_length=1)
    created_at: AwareDatetime
