from datetime import datetime

from pydantic import ConfigDict, Field, model_validator

from app.schemas.base import ApiModel
from app.schemas.team import SupportTeamResponse


class UserDocument(ApiModel):
    """Firestore users 문서에 저장되는 필드."""

    email: str
    nickname: str
    birth_year: int | None = None
    support_team_id: str
    profile_image_url: str | None = None
    onboarding_completed: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class UserBootstrapRequest(ApiModel):
    """최초 사용자 프로필 생성 요청."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "nickname": "민준",
                    "birthYear": 2002,
                    "supportTeamId": "LG",
                }
            ]
        }
    )

    nickname: str
    birth_year: int
    support_team_id: str


class UserUpdateRequest(ApiModel):
    """사용자 프로필 수정 요청."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "nickname": "민준",
                    "supportTeamId": "LG",
                }
            ]
        }
    )

    nickname: str | None = Field(
        default=None,
        min_length=1,
        description="변경할 닉네임",
    )
    support_team_id: str | None = Field(
        default=None,
        min_length=1,
        description="변경할 응원팀 ID",
    )

    @model_validator(mode="after")
    def validate_update_fields(self) -> "UserUpdateRequest":
        if (
            self.nickname is None
            and self.support_team_id is None
        ):
            raise ValueError(
                "수정할 사용자 정보를 하나 이상 입력해야 합니다."
            )

        return self


class UserResponse(ApiModel):
    """사용자 프로필 API 응답."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "userId": "firebase_uid_example",
                    "email": "user@example.com",
                    "nickname": "민준",
                    "birthYear": 2002,
                    "profileImageUrl": None,
                    "supportTeam": {
                        "teamId": "LG",
                        "name": "LG 트윈스",
                        "logoUrl": "https://example.com/lg.png",
                    },
                    "onboardingCompleted": True,
                    "createdAt": "2026-08-12T15:00:00+09:00",
                    "updatedAt": "2026-08-12T15:00:00+09:00",
                }
            ]
        }
    )

    user_id: str
    email: str
    nickname: str
    birth_year: int | None = None
    profile_image_url: str | None = None
    support_team: SupportTeamResponse
    onboarding_completed: bool
    created_at: datetime
    updated_at: datetime | None = None
