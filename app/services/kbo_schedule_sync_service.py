from dataclasses import dataclass
from datetime import datetime, timezone

from app.external.kbo.client import KboScheduleClient
from app.external.kbo.parser import parse_schedule_response
from app.repositories.game_repository import GameRepository
from app.schemas.game import GameDocument


@dataclass(frozen=True)
class KboScheduleSyncResult:
    fetched: int
    created: int
    updated: int
    skipped_rows: list[str]
    dry_run: bool


class KboScheduleSyncService:
    """KBO 월별 일정을 읽어 Firestore games 문서로 동기화한다."""

    def __init__(
        self,
        client: KboScheduleClient | None = None,
        repository: GameRepository | None = None,
    ) -> None:
        self._client = client or KboScheduleClient()
        self._repository = repository

    async def sync_month(
        self,
        year: int,
        month: int,
        *,
        dry_run: bool = True,
    ) -> KboScheduleSyncResult:
        response = await self._client.get_month_schedule(year, month)
        parsed = parse_schedule_response(response, year=year)

        if dry_run:
            return KboScheduleSyncResult(
                fetched=len(parsed.games),
                created=0,
                updated=0,
                skipped_rows=parsed.skipped_rows,
                dry_run=True,
            )

        repository = self._repository or GameRepository()
        now = datetime.now(timezone.utc)
        created = 0
        updated = 0

        for game in parsed.games:
            existing = repository.get_by_id(game.game_id)
            document = GameDocument(
                home_team_id=game.home_team_id,
                away_team_id=game.away_team_id,
                stadium_id=game.stadium_id,
                game_start_at=game.game_start_at,
                status=game.status,
                home_score=game.home_score,
                away_score=game.away_score,
                result_text=game.result_text,
                created_at=existing.created_at if existing else now,
                updated_at=now,
            )
            repository.set_game(game.game_id, document)
            if existing is None:
                created += 1
            else:
                updated += 1

        return KboScheduleSyncResult(
            fetched=len(parsed.games),
            created=created,
            updated=updated,
            skipped_rows=parsed.skipped_rows,
            dry_run=False,
        )
