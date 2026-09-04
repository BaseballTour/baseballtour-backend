from app.repositories.team_repository import (
    TeamRepository,
)
from app.schemas.team import (
    TeamDocument,
    TeamRecord,
    TeamResponse,
)
from app.services.storage_service import (
    StorageService,
)


def resolve_team_logo_url(
    team: TeamDocument | TeamRecord | TeamResponse,
    *,
    storage_service: StorageService | None = None,
) -> str | None:
    """
    구단 로고 API URL을 반환합니다.

    신규 데이터:
        logoStoragePath -> signed GET URL

    기존 데이터:
        logoUrl -> 그대로 반환
    """

    storage_path = getattr(
        team,
        "logo_storage_path",
        None,
    )

    if storage_path:
        service = (
            storage_service
            or StorageService()
        )

        return service.create_download_url(
            storage_path
        )

    return team.logo_url


class TeamService:
    """구단 관련 비즈니스 로직을 담당합니다."""

    def __init__(
        self,
        repository: TeamRepository | None = None,
        storage_service: StorageService | None = None,
    ) -> None:
        self._repository = (
            repository
            or TeamRepository()
        )

        self._storage_service = (
            storage_service
        )

    def get_teams(
        self,
    ) -> list[TeamResponse]:
        """전체 구단 목록을 반환합니다."""

        return [
            self._to_response(team)
            for team
            in self._repository.get_all()
        ]

    def get_team(
        self,
        team_id: str,
    ) -> TeamResponse | None:
        """구단 ID로 구단을 조회합니다."""

        team = self._repository.get_by_id(
            team_id
        )

        if team is None:
            return None

        return self._to_response(team)

    def team_exists(
        self,
        team_id: str,
    ) -> bool:
        """구단이 존재하는지 확인합니다."""

        return self._repository.exists(
            team_id
        )

    def _to_response(
        self,
        team: TeamRecord,
    ) -> TeamResponse:
        return TeamResponse(
            team_id=team.team_id,
            name=team.name,
            short_name=team.short_name,
            logo_url=resolve_team_logo_url(
                team,
                storage_service=(
                    self._storage_service
                ),
            ),
            home_region=team.home_region,
            stadium_id=team.stadium_id,
        )
