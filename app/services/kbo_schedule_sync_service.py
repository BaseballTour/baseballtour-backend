from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.external.kbo.client import KboScheduleClient
from app.external.kbo.parser import (
    parse_day_games_response,
    parse_schedule_response,
)
from app.repositories.game_repository import GameRepository
from app.schemas.game import GameDocument, GameStatus


KOREA_TIMEZONE = ZoneInfo("Asia/Seoul")
STATUS_MONITORING_LEAD_TIME = timedelta(hours=2)
TERMINAL_GAME_STATUSES = {
    GameStatus.COMPLETED,
    GameStatus.CANCELLED,
    GameStatus.POSTPONED,
}


@dataclass(frozen=True)
class KboScheduleSyncResult:
    fetched: int
    created: int
    updated: int
    unchanged: int
    skipped_rows: list[str]
    dry_run: bool
    skip_reason: str | None = None


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

    async def sync_day_status_if_needed(
        self,
        game_date: date,
        *,
        dry_run: bool = True,
        now: datetime | None = None,
    ) -> KboScheduleSyncResult:
        """Firestore 경기 상태를 보고 필요할 때만 KBO를 조회한다."""
        repository = self._repository or GameRepository()
        day_start = datetime.combine(
            game_date,
            time.min,
            tzinfo=KOREA_TIMEZONE,
        )
        day_end = day_start + timedelta(days=1)
        games = repository.get_by_date_range(
            start_at=day_start,
            end_at=day_end,
        )

        if not games:
            return self._skipped_status_result(
                dry_run=dry_run,
                reason="NO_GAMES_TODAY",
            )

        pending_games = [
            game
            for game in games
            if game.status not in TERMINAL_GAME_STATUSES
        ]
        if not pending_games:
            return self._skipped_status_result(
                dry_run=dry_run,
                reason="ALL_GAMES_TERMINAL",
            )

        current = now or datetime.now(KOREA_TIMEZONE)
        current = current.astimezone(KOREA_TIMEZONE)
        earliest_start = min(
            game.game_start_at.astimezone(KOREA_TIMEZONE)
            for game in pending_games
        )
        if current < earliest_start - STATUS_MONITORING_LEAD_TIME:
            return self._skipped_status_result(
                dry_run=dry_run,
                reason="BEFORE_MONITORING_WINDOW",
            )

        return await self.sync_day_status(game_date, dry_run=dry_run)

    @staticmethod
    def _skipped_status_result(
        *,
        dry_run: bool,
        reason: str,
    ) -> KboScheduleSyncResult:
        return KboScheduleSyncResult(
            fetched=0,
            created=0,
            updated=0,
            unchanged=0,
            skipped_rows=[],
            dry_run=dry_run,
            skip_reason=reason,
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
