from pathlib import Path

from firebase_admin import storage as firebase_storage

from app.core.config import settings
from app.repositories.team_repository import (
    TeamRepository,
)


TEAM_IDS = (
    "doosan",
    "lg",
    "kiwoom",
    "ssg",
    "kt",
    "hanwha",
    "kia",
    "samsung",
    "lotte",
    "nc",
)

DEFAULT_ASSET_DIR = Path(
    "assets/team-logos"
)

PNG_SIGNATURE = (
    b"\x89PNG\r\n\x1a\n"
)

MAX_LOGO_SIZE_BYTES = (
    5 * 1024 * 1024
)


def storage_path_for(
    team_id: str,
) -> str:
    return (
        f"teams/{team_id}/logo.png"
    )


def validate_assets(
    asset_dir: Path = DEFAULT_ASSET_DIR,
) -> dict[str, Path]:
    """업로드 전 10개 로고 파일을 전부 검증합니다."""

    assets = {
        team_id: (
            asset_dir
            / f"{team_id}.png"
        )
        for team_id in TEAM_IDS
    }

    missing = [
        str(path)
        for path in assets.values()
        if not path.is_file()
    ]

    if missing:
        formatted = "\n".join(
            f"- {item}"
            for item in missing
        )

        raise RuntimeError(
            "다음 구단 로고 파일이 없습니다:\n"
            f"{formatted}"
        )

    for team_id, path in assets.items():
        size = path.stat().st_size

        if size <= 0:
            raise RuntimeError(
                f"{team_id} 로고 파일이 비어 있습니다."
            )

        if size > MAX_LOGO_SIZE_BYTES:
            raise RuntimeError(
                f"{team_id} 로고 파일이 "
                "5MB를 초과합니다."
            )

        with path.open("rb") as file:
            signature = file.read(
                len(PNG_SIGNATURE)
            )

        if signature != PNG_SIGNATURE:
            raise RuntimeError(
                f"{team_id}.png가 실제 PNG "
                "파일이 아닙니다."
            )

    return assets


def ensure_safe_environment() -> None:
    environment = (
        settings.app_env
        .strip()
        .lower()
    )

    if environment in {
        "prod",
        "production",
    }:
        raise RuntimeError(
            "운영 환경에서는 이 개발용 "
            "업로드 스크립트를 실행할 수 없습니다."
        )


def upload_team_logos(
    asset_dir: Path = DEFAULT_ASSET_DIR,
) -> None:
    ensure_safe_environment()

    # 원격 작업 전에 로컬 10개 파일을
    # 먼저 전부 검증합니다.
    assets = validate_assets(
        asset_dir
    )

    repository = TeamRepository()

    missing_teams = [
        team_id
        for team_id in TEAM_IDS
        if not repository.exists(
            team_id
        )
    ]

    if missing_teams:
        raise RuntimeError(
            "Firestore에 없는 구단이 있습니다: "
            + ", ".join(missing_teams)
            + "\n먼저 "
            "`uv run python -m scripts.seed_teams`"
            "를 실행하세요."
        )

    bucket = firebase_storage.bucket()

    print(
        "Storage bucket =",
        bucket.name,
    )

    # -------------------------------------------------
    # 1단계: Storage 파일 10개 업로드
    #
    # 이 단계가 모두 성공하기 전까지
    # Firestore logoStoragePath는 변경하지 않습니다.
    # -------------------------------------------------

    for team_id in TEAM_IDS:
        source = assets[team_id]

        storage_path = (
            storage_path_for(
                team_id
            )
        )

        blob = bucket.blob(
            storage_path
        )

        blob.upload_from_filename(
            str(source),
            content_type="image/png",
        )

        blob.cache_control = (
            "public, max-age=86400"
        )

        blob.patch()

        print(
            "[Storage 업로드 완료]",
            storage_path,
        )

    # -------------------------------------------------
    # 2단계: Firestore 연결
    # -------------------------------------------------

    for team_id in TEAM_IDS:
        storage_path = (
            storage_path_for(
                team_id
            )
        )

        updated = (
            repository
            .update_logo_storage_path(
                team_id,
                storage_path,
            )
        )

        if not updated:
            raise RuntimeError(
                "Storage 업로드 후 Firestore "
                "구단 문서를 찾지 못했습니다: "
                f"{team_id}"
            )

        print(
            "[Firestore 연결 완료]",
            f"teams/{team_id}",
            "->",
            storage_path,
        )

    print(
        "\n10개 구단 로고 업로드 및 "
        "Firestore 연결 완료"
    )


if __name__ == "__main__":
    upload_team_logos()
