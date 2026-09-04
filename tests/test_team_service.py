from unittest.mock import Mock

from app.repositories.team_repository import (
    TeamRepository,
)
from app.schemas.team import (
    TeamRecord,
)
from app.services.storage_service import (
    StorageService,
)
from app.services.team_service import (
    TeamService,
)


def make_team(
    *,
    logo_url: str | None = None,
    logo_storage_path: str | None = None,
) -> TeamRecord:
    return TeamRecord(
        team_id="lg",
        name="LG 트윈스",
        short_name="LG",
        logo_url=logo_url,
        logo_storage_path=logo_storage_path,
        home_region="서울",
        stadium_id="jamsil",
    )


def test_get_team_uses_storage_logo() -> None:
    repository = Mock(
        spec=TeamRepository
    )

    storage_service = Mock(
        spec=StorageService
    )

    repository.get_by_id.return_value = (
        make_team(
            logo_storage_path=(
                "teams/lg/logo.png"
            )
        )
    )

    storage_service.create_download_url.return_value = (
        "https://storage.example/lg"
    )

    service = TeamService(
        repository=repository,
        storage_service=storage_service,
    )

    result = service.get_team("lg")

    assert result is not None

    assert (
        result.logo_url
        == "https://storage.example/lg"
    )

    storage_service.create_download_url.assert_called_once_with(
        "teams/lg/logo.png"
    )


def test_get_team_keeps_legacy_logo_url() -> None:
    repository = Mock(
        spec=TeamRepository
    )

    repository.get_by_id.return_value = (
        make_team(
            logo_url=(
                "https://legacy.example/lg.png"
            )
        )
    )

    service = TeamService(
        repository=repository,
    )

    result = service.get_team("lg")

    assert result is not None

    assert (
        result.logo_url
        == "https://legacy.example/lg.png"
    )
