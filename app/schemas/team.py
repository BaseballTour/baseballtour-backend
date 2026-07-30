from app.schemas.base import ApiModel


class TeamDocument(ApiModel):
    """Firestore teams 문서에 저장되는 필드."""

    name: str
    short_name: str
    logo_url: str
    home_region: str
    stadium_id: str


class TeamResponse(TeamDocument):
    """구단 API 응답 모델."""

    team_id: str


class SupportTeamResponse(ApiModel):
    """사용자 프로필에 포함되는 응원팀 요약 정보."""

    team_id: str
    name: str
    logo_url: str
