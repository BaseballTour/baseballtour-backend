import json
from pathlib import Path

import httpx
import pytest

from app.external.kbo.client import KBO_SCHEDULE_URL, KboScheduleClient
from app.external.kbo.parser import parse_schedule_response
from app.schemas.game import GameStatus
from app.services.kbo_schedule_sync_service import KboScheduleSyncService


FIXTURE = Path(__file__).parent / "fixtures" / "kbo_schedule_response.json"


def test_parse_kbo_schedule_response() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))

    result = parse_schedule_response(data, year=2026)

    assert len(result.games) == 2
    assert result.games[0].game_id == "kbo_20260801_lg_doosan_jamsil_1"
    assert result.games[0].status is GameStatus.COMPLETED
    assert result.games[0].away_score == 2
    assert result.games[0].home_score == 2
    assert result.games[0].game_start_at.isoformat() == "2026-08-01T18:00:00+09:00"
    assert result.games[1].status is GameStatus.CANCELLED
    assert result.games[1].result_text == "폭염취소"
    assert result.skipped_rows == [
        "row 3: 미지원 팀/구장 (KIA vs NC, 울산)"
    ]


@pytest.mark.anyio
async def test_kbo_schedule_client_posts_month_parameters() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == KBO_SCHEDULE_URL
        assert request.method == "POST"
        assert b"seasonId=2026" in request.content
        assert b"gameMonth=08" in request.content
        return httpx.Response(200, json={"rows": []})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        result = await KboScheduleClient(http_client).get_month_schedule(
            2026,
            8,
        )

    assert result == {"rows": []}


@pytest.mark.anyio
async def test_kbo_schedule_client_rejects_changed_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": []})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        with pytest.raises(ValueError, match="응답 구조가 변경"):
            await KboScheduleClient(http_client).get_month_schedule(2026, 8)


class _FixtureClient:
    async def get_month_schedule(self, year: int, month: int) -> dict:
        assert (year, month) == (2026, 8)
        return json.loads(FIXTURE.read_text(encoding="utf-8"))


class _MemoryGameRepository:
    def __init__(self) -> None:
        self.games: dict[str, object] = {}

    def get_by_id(self, game_id: str):
        return self.games.get(game_id)

    def set_game(self, game_id: str, game) -> None:
        self.games[game_id] = game


@pytest.mark.anyio
async def test_sync_is_dry_run_by_default() -> None:
    repository = _MemoryGameRepository()
    service = KboScheduleSyncService(_FixtureClient(), repository)

    result = await service.sync_month(2026, 8)

    assert result.dry_run is True
    assert result.fetched == 2
    assert repository.games == {}


@pytest.mark.anyio
async def test_sync_writes_and_then_updates_same_game_ids() -> None:
    repository = _MemoryGameRepository()
    service = KboScheduleSyncService(_FixtureClient(), repository)

    first = await service.sync_month(2026, 8, dry_run=False)
    created_at = repository.games[
        "kbo_20260801_lg_doosan_jamsil_1"
    ].created_at
    second = await service.sync_month(2026, 8, dry_run=False)

    assert (first.created, first.updated) == (2, 0)
    assert (second.created, second.updated) == (0, 2)
    assert repository.games[
        "kbo_20260801_lg_doosan_jamsil_1"
    ].created_at == created_at
