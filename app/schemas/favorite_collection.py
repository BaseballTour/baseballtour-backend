from pydantic import AwareDatetime, Field

from app.schemas.base import ApiModel


class FavoriteCollectionDocument(ApiModel):
    """구단 구분 없이 사용하는 사용자 개인 찜 컬렉션 문서."""

    name: str = Field(min_length=1)
    created_at: AwareDatetime
    updated_at: AwareDatetime


class FavoriteCollectionRecord(FavoriteCollectionDocument):
    collection_id: str = Field(min_length=1)


class FavoriteCollectionItemDocument(ApiModel):
    """장소 원본을 복제하지 않고 places 문서 ID만 참조한다."""

    place_id: str = Field(min_length=1)
    created_at: AwareDatetime
