from app.repositories.team_repository import TeamRepository
from app.schemas.team import TeamResponse


class TeamService:
    """구단 관련 비즈니스 로직을 담당합니다."""

    def __init__(
        self,
        repository: TeamRepository | None = None,
    ) -> None:
        self._repository = repository or TeamRepository()

    def get_teams(self) -> list[TeamResponse]:
        """전체 구단 목록을 반환합니다."""

        return self._repository.get_all()

    def get_team(self, team_id: str) -> TeamResponse | None:
        """구단 ID로 구단을 조회합니다."""

        return self._repository.get_by_id(team_id)

    def team_exists(self, team_id: str) -> bool:
        """구단이 존재하는지 확인합니다."""

        return self._repository.exists(team_id)
