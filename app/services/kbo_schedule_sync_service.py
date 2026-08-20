from dataclasses import dataclass
from datetime import date, datetime, timezone

from app.external.kbo.client import KboScheduleClient
from app.external.kbo.parser import (
    parse_day_games_response,
    parse_schedule_response,
)
from app.repositories.game_repository import GameRepository
from app.schemas.game import GameDocument


@dataclass(frozen=True)
class KboScheduleSyncResult:
    fetched: int
    created: int
    updated: int
    unchanged: int
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
                unchanged=0,
                skipped_rows=parsed.skipped_rows,
                dry_run=True,
            )

        repository = self._repository or GameRepository()
        now = datetime.now(timezone.utc)
        created = 0
        updated = 0
        unchanged = 0

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
            if existing is not None and self._same_game(existing, document):
                unchanged += 1
                continue
            repository.set_game(game.game_id, document)
            if existing is None:
                created += 1
            else:
                updated += 1

        return KboScheduleSyncResult(
            fetched=len(parsed.games),
            created=created,
            updated=updated,
            unchanged=unchanged,
            skipped_rows=parsed.skipped_rows,
            dry_run=False,
        )

    async def sync_horizon(
        self,
        start_date: date,
        *,
        months_ahead: int = 2,
        dry_run: bool = True,
    ) -> KboScheduleSyncResult:
        """현재 월부터 향후 N개월까지 순차적으로 동기화한다."""
        if not 0 <= months_ahead <= 12:
            raise ValueError("months_ahead는 0부터 12 사이여야 합니다.")

        results: list[KboScheduleSyncResult] = []
        month_index = start_date.year * 12 + start_date.month - 1
        for offset in range(months_ahead + 1):
            target = month_index + offset
            year, zero_based_month = divmod(target, 12)
            results.append(
                await self.sync_month(
                    year,
                    zero_based_month + 1,
                    dry_run=dry_run,
                )
            )
        return self._combine(results, dry_run=dry_run)

    async def sync_day_status(
        self,
        game_date: date,
        *,
        dry_run: bool = True,
    ) -> KboScheduleSyncResult:
        """하루 경기의 취소·연기·종료 결과만 효율적으로 갱신한다."""
        response = await self._client.get_day_games(game_date.strftime("%Y%m%d"))
        parsed = parse_day_games_response(response)
        if dry_run:
            return KboScheduleSyncResult(
                fetched=len(parsed.games),
                created=0,
                updated=0,
                unchanged=0,
                skipped_rows=parsed.skipped_rows,
                dry_run=True,
            )

        repository = self._repository or GameRepository()
        now = datetime.now(timezone.utc)
        created = updated = unchanged = 0
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
            if existing is not None and self._same_game(existing, document):
                unchanged += 1
                continue
            repository.set_game(game.game_id, document)
            if existing is None:
                created += 1
            else:
                updated += 1
        return KboScheduleSyncResult(
            fetched=len(parsed.games),
            created=created,
            updated=updated,
            unchanged=unchanged,
            skipped_rows=parsed.skipped_rows,
            dry_run=False,
        )

    @staticmethod
    def _same_game(existing, document: GameDocument) -> bool:
        fields = (
            "home_team_id",
            "away_team_id",
            "stadium_id",
            "game_start_at",
            "status",
            "home_score",
            "away_score",
            "result_text",
        )
        return all(
            getattr(existing, field) == getattr(document, field)
            for field in fields
        )

    @staticmethod
    def _combine(
        results: list[KboScheduleSyncResult],
        *,
        dry_run: bool,
    ) -> KboScheduleSyncResult:
        return KboScheduleSyncResult(
            fetched=sum(result.fetched for result in results),
            created=sum(result.created for result in results),
            updated=sum(result.updated for result in results),
            unchanged=sum(result.unchanged for result in results),
            skipped_rows=[
                reason
                for result in results
                for reason in result.skipped_rows
            ],
            dry_run=dry_run,
        )
