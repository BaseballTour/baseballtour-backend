from pydantic import AwareDatetime, Field

from app.models.place import Place
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
    is_default: bool = Field(
        default=False,
        description="시스템 기본 찜 컬렉션 여부",
    )
    created_at: AwareDatetime
    updated_at: AwareDatetime


class FavoriteCollectionRecord(FavoriteCollectionDocument):
    """Firestore에서 조회한 개인 찜 컬렉션."""

    collection_id: str = Field(min_length=1)


class FavoriteCollectionResponse(ApiModel):
    """개인 찜 컬렉션 API 응답."""

    collection_id: str
    name: str
    is_default: bool = Field(
        default=False,
        description="시스템 기본 찜 컬렉션 여부",
    )
    thumbnail_url: str | None = Field(
        default=None,
        description="컬렉션 첫 장소의 대표 이미지",
    )
    place_count: int = Field(
        default=0,
        ge=0,
        description="컬렉션에 저장된 장소 개수",
    )
    representative_place_name: str | None = Field(
        default=None,
        description="컬렉션 첫 장소의 이름",
    )
    created_at: AwareDatetime
    updated_at: AwareDatetime


class FavoriteCollectionItemDocument(ApiModel):
    """찜 장소 ID와 조회 장애에 대비한 장소 스냅샷."""

    place_id: str = Field(min_length=1)
    place_snapshot: Place | None = Field(
        default=None,
        description=(
            "찜 저장 시점의 장소 정보. 기존 ID 전용 문서와의 "
            "호환을 위해 null을 허용합니다."
        ),
    )
    created_at: AwareDatetime


class FavoriteCollectionItemResponse(ApiModel):
    """개인 찜 장소 API 응답."""

    place_id: str
    created_at: AwareDatetime


class FavoritePlaceCollectionsResponse(ApiModel):
    """특정 장소가 저장된 개인 찜 컬렉션 목록."""

    place_id: str
    collection_ids: list[str]
    count: int = Field(ge=0)
