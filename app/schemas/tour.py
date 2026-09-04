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


class TourFilterOption(ApiModel):
    filter_id: str = Field(description="프론트가 검색 요청에 전달할 필터 ID")
    label: str = Field(description="화면에 표시할 한글명")
    group: str = Field(description="필터가 속한 상위 화면 그룹")
    classification_codes: list[str] = Field(
        description="백엔드가 조합하는 TourAPI 신분류 코드"
    )
