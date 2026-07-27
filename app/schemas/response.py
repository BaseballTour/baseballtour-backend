from typing import Any, Generic, Literal, TypeVar

from pydantic import Field

from app.schemas.base import ApiModel


DataT = TypeVar("DataT")


class SuccessResponse(ApiModel, Generic[DataT]):
    success: Literal[True] = True
    data: DataT


class ListMeta(ApiModel):
    count: int = Field(
        ge=0,
        description="현재 응답에 포함된 데이터 개수",
    )
    next_page_token: str | None = Field(
        default=None,
        description="다음 페이지 조회 토큰",
    )


class ListSuccessResponse(ApiModel, Generic[DataT]):
    success: Literal[True] = True
    data: list[DataT]
    meta: ListMeta


class ErrorDetail(ApiModel):
    field: str
    reason: str


class ErrorBody(ApiModel):
    code: str
    message: str
    details: list[ErrorDetail] | list[Any] = Field(
        default_factory=list,
    )


class ErrorResponse(ApiModel):
    success: Literal[False] = False
    error: ErrorBody
