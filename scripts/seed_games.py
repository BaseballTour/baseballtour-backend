from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.repositories.game_repository import GameRepository
from app.repositories.stadium_repository import StadiumRepository
from app.repositories.team_repository import TeamRepository
from app.schemas.game import GameDocument, GameStatus


KOREA_TIMEZONE = ZoneInfo("Asia/Seoul")


def build_games() -> dict[str, GameDocument]:
    """개발 및 API 연동 테스트용 경기 데이터를 생성합니다."""

    now = datetime.now(timezone.utc)

    return {
        "dev_game_20260801_hanwha_kt": GameDocument(
            home_team_id="hanwha",
            away_team_id="kt",
            stadium_id="daejeon",
            game_start_at=datetime(
                2026,
                8,
                1,
                18,
                0,
                tzinfo=KOREA_TIMEZONE,
            ),
            status=GameStatus.COMPLETED,
            home_score=4,
            away_score=2,
            result_text="한화 이글스 승",
            created_at=now,
            updated_at=now,
        ),
        "dev_game_20260815_lotte_doosan": GameDocument(
            home_team_id="lotte",
            away_team_id="doosan",
            stadium_id="sajik",
            game_start_at=datetime(
                2026,
                8,
                15,
                18,
                0,
                tzinfo=KOREA_TIMEZONE,
            ),
            status=GameStatus.SCHEDULED,
            home_score=None,
            away_score=None,
            result_text=None,
            created_at=now,
            updated_at=now,
        ),
        "dev_game_20260815_nc_lg": GameDocument(
            home_team_id="nc",
            away_team_id="lg",
            stadium_id="changwon",
            game_start_at=datetime(
                2026,
                8,
                15,
                18,
                0,
                tzinfo=KOREA_TIMEZONE,
            ),
            status=GameStatus.SCHEDULED,
            home_score=None,
            away_score=None,
            result_text=None,
            created_at=now,
            updated_at=now,
        ),
        "dev_game_20260816_kia_samsung": GameDocument(
            home_team_id="kia",
            away_team_id="samsung",
            stadium_id="gwangju",
            game_start_at=datetime(
                2026,
                8,
                16,
                17,
                0,
                tzinfo=KOREA_TIMEZONE,
            ),
            status=GameStatus.SCHEDULED,
            home_score=None,
            away_score=None,
            result_text=None,
            created_at=now,
            updated_at=now,
        ),
        "dev_game_20260816_kiwoom_ssg": GameDocument(
            home_team_id="kiwoom",
            away_team_id="ssg",
            stadium_id="gocheok",
            game_start_at=datetime(
                2026,
                8,
                16,
                17,
                0,
                tzinfo=KOREA_TIMEZONE,
            ),
            status=GameStatus.POSTPONED,
            home_score=None,
            away_score=None,
            result_text="경기 연기",
            created_at=now,
            updated_at=now,
        ),
    }


def validate_references(
    games: dict[str, GameDocument],
    team_repository: TeamRepository,
    stadium_repository: StadiumRepository,
) -> None:
    """경기가 참조하는 구단과 구장이 존재하는지 확인합니다."""

    errors: list[str] = []

    for game_id, game in games.items():
        if not team_repository.exists(game.home_team_id):
            errors.append(
                f"{game_id}: 홈팀 없음 ({game.home_team_id})"
            )

        if not team_repository.exists(game.away_team_id):
            errors.append(
                f"{game_id}: 원정팀 없음 ({game.away_team_id})"
            )

        if not stadium_repository.exists(game.stadium_id):
            errors.append(
                f"{game_id}: 구장 없음 ({game.stadium_id})"
            )

    if errors:
        joined_errors = "\n".join(errors)

        raise RuntimeError(
            "경기 참조 데이터 검증에 실패했습니다.\n"
            f"{joined_errors}"
        )


def seed_games() -> None:
    """Firestore games Collection에 개발용 경기를 저장합니다."""

    if settings.app_env.lower() == "production":
        raise RuntimeError(
            "운영 환경에서는 개발용 경기 Seed를 실행할 수 없습니다."
        )

    game_repository = GameRepository()
    team_repository = TeamRepository()
    stadium_repository = StadiumRepository()

    games = build_games()

    validate_references(
        games,
        team_repository,
        stadium_repository,
    )

    print("구단·구장 참조 검증 완료\n")

    for game_id, game in games.items():
        game_repository.set_game(
            game_id,
            game,
        )

        korea_start_at = game.game_start_at.astimezone(
            KOREA_TIMEZONE
        )

        print(
            f"[저장 완료] games/{game_id}: "
            f"{game.home_team_id} vs {game.away_team_id} / "
            f"{korea_start_at.isoformat()} / "
            f"{game.status.value}"
        )

    print(
        f"\n총 {len(games)}개 개발용 경기 데이터 저장 완료"
    )


if __name__ == "__main__":
    seed_games()
