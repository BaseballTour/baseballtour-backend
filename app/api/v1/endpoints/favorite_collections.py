from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response, status

from app.api.dependencies.auth import (
    get_current_active_user_id,
)
from app.schemas.favorite_collection import (
    FavoriteCollectionCreateRequest,
    FavoriteCollectionItemDocument,
    FavoriteCollectionItemResponse,
    FavoriteCollectionRecord,
    FavoriteCollectionResponse,
    FavoriteCollectionUpdateRequest,
)
from app.schemas.response import (
    ListMeta,
    ListSuccessResponse,
    SuccessResponse,
)
from app.models.place import Place
from app.services.favorite_collection_service import (
    FavoriteCollectionService,
)


router = APIRouter(
    prefix="/users/me/favorite-collections",
)


def to_favorite_collection_response(
    collection: FavoriteCollectionRecord,
    thumbnail_url: str | None = None,
) -> FavoriteCollectionResponse:
    return FavoriteCollectionResponse(
        collection_id=collection.collection_id,
        name=collection.name,
        thumbnail_url=thumbnail_url,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


def to_favorite_collection_item_response(
    item: FavoriteCollectionItemDocument,
) -> FavoriteCollectionItemResponse:
    return FavoriteCollectionItemResponse(
        place_id=item.place_id,
        created_at=item.created_at,
    )


@router.post(
    "",
    response_model=SuccessResponse[FavoriteCollectionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="개인 찜 컬렉션 생성",
)
def create_favorite_collection(
    request: FavoriteCollectionCreateRequest,
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> SuccessResponse[FavoriteCollectionResponse]:
    service = FavoriteCollectionService()

    collection = service.create_collection(
        user_id=user_id,
        request=request,
    )

    return SuccessResponse(
        data=to_favorite_collection_response(
            collection
        )
    )


@router.get(
    "",
    response_model=ListSuccessResponse[FavoriteCollectionResponse],
    summary="개인 찜 컬렉션 목록 조회",
)
async def get_favorite_collections(
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> ListSuccessResponse[FavoriteCollectionResponse]:
    service = FavoriteCollectionService()

    collections = service.get_collections(
        user_id=user_id,
    )
    thumbnails = await service.get_collection_thumbnails(
        user_id=user_id,
        collections=collections,
    )

    data = [
        to_favorite_collection_response(
            collection,
            thumbnails.get(collection.collection_id),
        )
        for collection in collections
    ]

    return ListSuccessResponse(
        data=data,
        meta=ListMeta(
            count=len(data),
            next_page_token=None,
        ),
    )


@router.get(
    "/{collectionId}",
    response_model=ListSuccessResponse[Place],
    summary="개인 찜 컬렉션 장소 목록 조회",
)
async def get_favorite_collection_places(
    collection_id: Annotated[
        str,
        Path(alias="collectionId", description="찜 컬렉션 ID"),
    ],
    user_id: Annotated[str, Depends(get_current_active_user_id)],
) -> ListSuccessResponse[Place]:
    places = await FavoriteCollectionService().get_collection_places(
        user_id=user_id,
        collection_id=collection_id,
    )
    return ListSuccessResponse(
        data=places,
        meta=ListMeta(count=len(places), next_page_token=None),
    )


@router.patch(
    "/{collectionId}",
    response_model=SuccessResponse[FavoriteCollectionResponse],
    summary="개인 찜 컬렉션 이름 변경",
)
def update_favorite_collection(
    collection_id: Annotated[
        str,
        Path(
            alias="collectionId",
            description="찜 컬렉션 ID",
        ),
    ],
    request: FavoriteCollectionUpdateRequest,
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> SuccessResponse[FavoriteCollectionResponse]:
    service = FavoriteCollectionService()

    collection = service.update_collection(
        user_id=user_id,
        collection_id=collection_id,
        request=request,
    )

    return SuccessResponse(
        data=to_favorite_collection_response(
            collection
        )
    )


@router.delete(
    "/{collectionId}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="개인 찜 컬렉션 삭제",
)
def delete_favorite_collection(
    collection_id: Annotated[
        str,
        Path(
            alias="collectionId",
            description="찜 컬렉션 ID",
        ),
    ],
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> Response:
    service = FavoriteCollectionService()

    service.delete_collection(
        user_id=user_id,
        collection_id=collection_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )


@router.put(
    "/{collectionId}/items/{placeId}",
    response_model=SuccessResponse[FavoriteCollectionItemResponse],
    summary="찜 장소 저장",
    description=(
        "개인 찜 컬렉션에 TourAPI 기반 장소를 저장합니다. "
        "동일 장소를 다시 저장해도 중복 문서를 생성하지 않습니다."
    ),
)
def save_favorite_collection_item(
    collection_id: Annotated[
        str,
        Path(
            alias="collectionId",
            description="찜 컬렉션 ID",
        ),
    ],
    place_id: Annotated[
        str,
        Path(
            alias="placeId",
            description="찜할 장소 ID",
        ),
    ],
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> SuccessResponse[FavoriteCollectionItemResponse]:
    service = FavoriteCollectionService()

    item = service.save_item(
        user_id=user_id,
        collection_id=collection_id,
        place_id=place_id,
    )

    return SuccessResponse(
        data=to_favorite_collection_item_response(item)
    )


@router.delete(
    "/{collectionId}/items/{placeId}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="찜 장소 삭제",
)
def delete_favorite_collection_item(
    collection_id: Annotated[
        str,
        Path(
            alias="collectionId",
            description="찜 컬렉션 ID",
        ),
    ],
    place_id: Annotated[
        str,
        Path(
            alias="placeId",
            description="찜한 장소 ID",
        ),
    ],
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> Response:
    service = FavoriteCollectionService()

    service.delete_item(
        user_id=user_id,
        collection_id=collection_id,
        place_id=place_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )
