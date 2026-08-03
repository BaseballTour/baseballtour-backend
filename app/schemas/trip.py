from enum import Enum

from pydantic import AwareDatetime, Field, model_validator

from app.schemas.base import ApiModel


class TripStatus(str, Enum):
    """여행 진행 상태."""

    PLANNING = "PLANNING"
    GENERATING = "GENERATING"
    GENERATED = "GENERATED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TripPoint(ApiModel):
    """여행의 도착 또는 출발 장소."""

    name: str = Field(
        min_length=1,
        description="장소 이름",
    )
    latitude: float = Field(
        ge=-90,
        le=90,
        description="위도",
    )
    longitude: float = Field(
        ge=-180,
        le=180,
        description="경도",
    )


class AccommodationInfo(ApiModel):
    """여행 숙소 정보."""

    name: str = Field(
        min_length=1,
        description="숙소 이름",
    )
    address: str = Field(
        min_length=1,
        description="숙소 주소",
    )
    latitude: float = Field(
        ge=-90,
        le=90,
        description="숙소 위도",
    )
    longitude: float = Field(
        ge=-180,
        le=180,
        description="숙소 경도",
    )
    check_in_at: AwareDatetime
    check_out_at: AwareDatetime

    @model_validator(mode="after")
    def validate_stay_period(
        self,
    ) -> "AccommodationInfo":
        if self.check_out_at <= self.check_in_at:
            raise ValueError(
                "숙소 체크아웃 시간은 체크인 시간보다 늦어야 합니다."
            )

        return self


class TripCreateRequest(ApiModel):
    """여행 생성 요청."""

    game_id: str = Field(
        min_length=1,
        description="관람할 경기 ID",
    )
    title: str = Field(
        min_length=1,
        description="여행 제목",
    )
    trip_start_at: AwareDatetime
    trip_end_at: AwareDatetime

    arrival_point: TripPoint | None = None
    departure_point: TripPoint | None = None
    accommodation: AccommodationInfo | None = None

    @model_validator(mode="after")
    def validate_trip_period(
        self,
    ) -> "TripCreateRequest":
        if self.trip_end_at <= self.trip_start_at:
            raise ValueError(
                "여행 종료시간은 시작시간보다 늦어야 합니다."
            )

        return self


class TripUpdateRequest(ApiModel):
    """여행 기본정보 수정 요청."""

    game_id: str | None = Field(
        default=None,
        min_length=1,
    )
    title: str | None = Field(
        default=None,
        min_length=1,
    )
    trip_start_at: AwareDatetime | None = None
    trip_end_at: AwareDatetime | None = None

    arrival_point: TripPoint | None = None
    departure_point: TripPoint | None = None
    accommodation: AccommodationInfo | None = None

    @model_validator(mode="after")
    def validate_provided_trip_period(
        self,
    ) -> "TripUpdateRequest":
        if (
            self.trip_start_at is not None
            and self.trip_end_at is not None
            and self.trip_end_at <= self.trip_start_at
        ):
            raise ValueError(
                "여행 종료시간은 시작시간보다 늦어야 합니다."
            )

        return self


class TripDocument(ApiModel):
    """Firestore trips 문서에 저장되는 필드."""

    user_id: str = Field(
        min_length=1,
        description="여행 소유자 Firebase UID",
    )
    game_id: str = Field(
        min_length=1,
        description="관람할 경기 ID",
    )
    title: str = Field(
        min_length=1,
        description="여행 제목",
    )
    trip_start_at: AwareDatetime
    trip_end_at: AwareDatetime

    arrival_point: TripPoint | None = None
    departure_point: TripPoint | None = None
    accommodation: AccommodationInfo | None = None

    status: TripStatus = TripStatus.PLANNING
    active_plan_id: str | None = None

    created_at: AwareDatetime
    updated_at: AwareDatetime

    @model_validator(mode="after")
    def validate_trip_period(
        self,
    ) -> "TripDocument":
        if self.trip_end_at <= self.trip_start_at:
            raise ValueError(
                "여행 종료시간은 시작시간보다 늦어야 합니다."
            )

        return self


class TripRecord(TripDocument):
    """Firestore에서 조회한 여행 문서."""

    trip_id: str


class TripSummaryResponse(ApiModel):
    """여행 생성 및 목록 조회 응답."""

    trip_id: str
    game_id: str
    title: str
    status: TripStatus
    trip_start_at: AwareDatetime
    trip_end_at: AwareDatetime
    created_at: AwareDatetime


class TripDetailResponse(TripSummaryResponse):
    """여행 상세 및 수정 응답."""

    arrival_point: TripPoint | None = None
    departure_point: TripPoint | None = None
    accommodation: AccommodationInfo | None = None
    active_plan_id: str | None = None
    updated_at: AwareDatetime
