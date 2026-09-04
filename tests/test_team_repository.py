from unittest.mock import Mock

from app.repositories.team_repository import (
    TeamRepository,
)


def test_get_by_id_returns_storage_path() -> None:
    client = Mock()

    collection = (
        client.collection.return_value
    )

    snapshot = (
        collection
        .document.return_value
        .get.return_value
    )

    snapshot.exists = True
    snapshot.id = "lg"

    snapshot.to_dict.return_value = {
        "name": "LG 트윈스",
        "shortName": "LG",
        "logoUrl": None,
        "logoStoragePath": (
            "teams/lg/logo.png"
        ),
        "homeRegion": "서울",
        "stadiumId": "jamsil",
    }

    repository = TeamRepository(
        client=client
    )

    team = repository.get_by_id(
        "lg"
    )

    assert team is not None
    assert team.team_id == "lg"
    assert (
        team.logo_storage_path
        == "teams/lg/logo.png"
    )


def test_update_logo_storage_path() -> None:
    client = Mock()

    collection = (
        client.collection.return_value
    )

    reference = (
        collection.document.return_value
    )

    reference.get.return_value.exists = True

    repository = TeamRepository(
        client=client
    )

    result = (
        repository.update_logo_storage_path(
            "lg",
            "teams/lg/logo.png",
        )
    )

    assert result is True

    reference.update.assert_called_once_with(
        {
            "logoStoragePath": (
                "teams/lg/logo.png"
            ),
            "logoUrl": None,
        }
    )
