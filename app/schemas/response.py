from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field


DataT = TypeVar("DataT")


class SuccessResponse(BaseModel, Generic[DataT]):
    model_config = ConfigDict(extra="forbid")

    success: Literal[True] = Field(
        default=True,
        description="요청 성공 여부",
    )
    message: str = Field(
        description="응답 메시지",
    )
    data: DataT


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: Literal[False] = Field(
        default=False,
        description="요청 성공 여부",
    )
    code: str = Field(
        description="애플리케이션 오류 코드",
    )
    message: str = Field(
        description="사용자에게 제공할 오류 메시지",
    )
    details: Any | None = Field(
        default=None,
        description="추가 오류 정보",
    )
