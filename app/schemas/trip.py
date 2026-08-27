from enum import Enum

from pydantic import AwareDatetime, ConfigDict, Field, model_validator

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
    kakao_place_id: str | None = Field(
        default=None,
        description="Kakao 장소 검색으로 선택한 경우의 장소 ID",
    )


class TripCreateRequest(ApiModel):
    """여행 생성 요청."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "gameId": "game_20260815_lg_doosan",
                    "title": "잠실 원정 직관 여행",
                    "tripStartAt": "2026-08-15T12:00:00+09:00",
                    "tripEndAt": "2026-08-15T23:00:00+09:00",
                    "arrivalPoint": {
                        "name": "서울역",
                        "latitude": 37.5547,
                        "longitude": 126.9706,
                    },
                    "departurePoint": {
                        "name": "서울역",
                        "latitude": 37.5547,
                        "longitude": 126.9706,
                    },
                    "accommodation": None,
                }
            ]
        }
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

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "잠실 1박 2일 직관 여행",
                    "tripEndAt": "2026-08-16T11:00:00+09:00",
                    "accommodation": {
                        "name": "잠실 호텔",
                        "address": "서울특별시 송파구",
                        "latitude": 37.513,
                        "longitude": 127.102,
                    },
                }
            ]
        }
    )

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
    rejected_recommendation_place_ids: list[str] = Field(
        default_factory=list,
        description="재생성에서 다시 제안하지 않을 자동 추천 장소 ID",
    )
    idempotency_request_hash: str | None = Field(
        default=None,
        description="여행 생성 중복 요청 검증용 요청 해시",
    )

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
