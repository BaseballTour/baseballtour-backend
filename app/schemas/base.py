from datetime import datetime
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    field_validator,
)

from app.core.time import to_korea_datetime


def to_camel(value: str) -> str:
    parts = value.split("_")

    return parts[0] + "".join(
        part.capitalize()
        for part in parts[1:]
    )


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
    )

    @field_validator("*", mode="after", check_fields=False)
    @classmethod
    def normalize_datetime_to_korea(cls, value: Any) -> Any:
        """요청·Firestore 입력의 datetime을 한국시간으로 정규화한다."""
        if isinstance(value, datetime):
            return to_korea_datetime(value)
        return value
