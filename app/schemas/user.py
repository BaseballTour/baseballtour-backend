from datetime import datetime

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


class UserBootstrapRequest(ApiModel):
    """최초 사용자 프로필 생성 요청."""

    nickname: str
    birth_year: int
    support_team_id: str


class SupportTeamUpdateRequest(ApiModel):
    """응원팀 설정 및 변경 요청."""

    support_team_id: str


class UserResponse(ApiModel):
    """사용자 프로필 API 응답."""

    user_id: str
    email: str
    nickname: str
    birth_year: int | None = None
    profile_image_url: str | None = None
    support_team: SupportTeamResponse
    onboarding_completed: bool
    created_at: datetime
    updated_at: datetime | None = None
