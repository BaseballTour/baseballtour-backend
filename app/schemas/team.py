from app.schemas.base import ApiModel


class TeamDocument(ApiModel):
    """Firestore teams 문서에 저장되는 필드."""

    name: str
    short_name: str

    # 기존 URL 기반 Firestore 데이터 호환용입니다.
    logo_url: str | None = None

    # 신규 로고는 Storage 경로를 기준 데이터로 사용합니다.
    logo_storage_path: str | None = None

    home_region: str
    stadium_id: str


class TeamRecord(TeamDocument):
    """Firestore에서 조회한 구단 문서."""

    team_id: str


class TeamResponse(ApiModel):
    """구단 API 응답 모델."""

    team_id: str
    name: str
    short_name: str
    logo_url: str | None = None
    home_region: str
    stadium_id: str


class SupportTeamResponse(ApiModel):
    """사용자 프로필에 포함되는 응원팀 요약 정보."""

    team_id: str
    name: str
    logo_url: str | None = None
