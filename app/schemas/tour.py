from pydantic import Field

from app.schemas.base import ApiModel


class TourClassification(ApiModel):
    lcls_system1: str = Field(
        description="TourAPI 신분류 대분류 코드"
    )
    lcls_system1_name: str = Field(
        description="TourAPI 신분류 대분류 한글명"
    )
    lcls_system2: str | None = Field(
        default=None,
        description="TourAPI 신분류 중분류 코드",
    )
    lcls_system2_name: str | None = Field(
        default=None,
        description="TourAPI 신분류 중분류 한글명",
    )
    lcls_system3: str | None = Field(
        default=None,
        description="TourAPI 신분류 소분류 코드",
    )
    lcls_system3_name: str | None = Field(
        default=None,
        description="TourAPI 신분류 소분류 한글명",
    )
