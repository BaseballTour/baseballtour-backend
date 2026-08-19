from datetime import datetime

from pydantic import ConfigDict

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


class SupportTeamUpdateRequest(ApiModel):
    """응원팀 설정 및 변경 요청."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "supportTeamId": "LG",
                }
            ]
        }
    )

    support_team_id: str


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
