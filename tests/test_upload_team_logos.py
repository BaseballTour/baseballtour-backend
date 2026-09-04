from pathlib import Path

import pytest

from scripts.upload_team_logos import (
    PNG_SIGNATURE,
    TEAM_IDS,
    storage_path_for,
    validate_assets,
)


def write_png(
    path: Path,
) -> None:
    path.write_bytes(
        PNG_SIGNATURE
        + b"test-png-data"
    )


def test_storage_path_for_team() -> None:
    assert (
        storage_path_for("lg")
        == "teams/lg/logo.png"
    )


def test_validate_assets_accepts_all_teams(
    tmp_path: Path,
) -> None:
    for team_id in TEAM_IDS:
        write_png(
            tmp_path
            / f"{team_id}.png"
        )

    result = validate_assets(
        tmp_path
    )

    assert set(result) == set(
        TEAM_IDS
    )


def test_validate_assets_rejects_missing_logo(
    tmp_path: Path,
) -> None:
    for team_id in TEAM_IDS[:-1]:
        write_png(
            tmp_path
            / f"{team_id}.png"
        )

    with pytest.raises(
        RuntimeError,
        match="로고 파일이 없습니다",
    ):
        validate_assets(
            tmp_path
        )


def test_validate_assets_rejects_fake_png(
    tmp_path: Path,
) -> None:
    for team_id in TEAM_IDS:
        write_png(
            tmp_path
            / f"{team_id}.png"
        )

    (
        tmp_path
        / "lg.png"
    ).write_bytes(
        b"not-a-png"
    )

    with pytest.raises(
        RuntimeError,
        match="실제 PNG",
    ):
        validate_assets(
            tmp_path
        )
