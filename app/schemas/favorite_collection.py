from pydantic import AwareDatetime, Field

from app.schemas.base import ApiModel


class FavoriteCollectionCreateRequest(ApiModel):
    """개인 찜 컬렉션 생성 요청."""

    name: str = Field(
        min_length=1,
        description="개인 찜 컬렉션 이름",
    )


class FavoriteCollectionUpdateRequest(ApiModel):
    """개인 찜 컬렉션 이름 변경 요청."""

    name: str = Field(
        min_length=1,
        description="변경할 개인 찜 컬렉션 이름",
    )


class FavoriteCollectionDocument(ApiModel):
    """구단 구분 없이 사용하는 사용자 개인 찜 컬렉션 문서."""

    name: str = Field(min_length=1)
    created_at: AwareDatetime
    updated_at: AwareDatetime


class FavoriteCollectionRecord(FavoriteCollectionDocument):
    """Firestore에서 조회한 개인 찜 컬렉션."""

    collection_id: str = Field(min_length=1)


class FavoriteCollectionResponse(ApiModel):
    """개인 찜 컬렉션 API 응답."""

    collection_id: str
    name: str
    thumbnail_url: str | None = Field(
        default=None,
        description="컬렉션 첫 장소의 대표 이미지",
    )
    created_at: AwareDatetime
    updated_at: AwareDatetime


class FavoriteCollectionItemDocument(ApiModel):
    """장소 원본을 복제하지 않고 places 문서 ID만 참조한다."""

    place_id: str = Field(min_length=1)
    created_at: AwareDatetime


class FavoriteCollectionItemResponse(ApiModel):
    """개인 찜 장소 API 응답."""

    place_id: str
    created_at: AwareDatetime
