from typing import Any

import httpx


KBO_SCHEDULE_URL = (
    "https://www.koreabaseball.com/ws/Schedule.asmx/"
    "GetScheduleList"
)
KBO_DAY_GAMES_URL = (
    "https://www.koreabaseball.com/ws/Main.asmx/GetKboGameList"
)
KBO_SCHEDULE_REFERER = (
    "https://www.koreabaseball.com/Schedule/Schedule.aspx"
)


class KboScheduleClient:
    """KBO 홈페이지가 사용하는 월별 일정 요청을 호출한다.

    공개 OpenAPI 계약이 아닌 홈페이지 내부 인터페이스이므로 사용자 요청
    경로에서 직접 호출하지 않고 저빈도 배치 동기화에만 사용한다.
    """

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        timeout_seconds: float = 15.0,
    ) -> None:
        self._client = client
        self._timeout_seconds = timeout_seconds

    async def get_month_schedule(
        self,
        year: int,
        month: int,
    ) -> dict[str, Any]:
        if year < 2000:
            raise ValueError("year는 2000 이상이어야 합니다.")
        if not 1 <= month <= 12:
            raise ValueError("month는 1부터 12 사이여야 합니다.")

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=self._timeout_seconds,
        )

        try:
            response = await client.post(
                KBO_SCHEDULE_URL,
                data={
                    "leId": "1",
                    "srIdList": "0,9",
                    "seasonId": str(year),
                    "gameMonth": f"{month:02d}",
                    "teamId": "",
                },
                headers={
                    "Accept": "application/json, text/javascript, */*",
                    "Referer": KBO_SCHEDULE_REFERER,
                    "User-Agent": "BaseballTour-MVP/0.1 schedule-sync",
                },
            )
            response.raise_for_status()
            data = response.json()
        finally:
            if owns_client:
                await client.aclose()

        if not isinstance(data, dict) or not isinstance(
            data.get("rows"), list
        ):
            raise ValueError("KBO 일정 응답 구조가 변경되었습니다.")

        return data

    async def get_day_games(self, game_date: str) -> dict[str, Any]:
        """YYYYMMDD 날짜의 경기 상태 목록을 조회한다."""
        if len(game_date) != 8 or not game_date.isdigit():
            raise ValueError("game_date는 YYYYMMDD 형식이어야 합니다.")

        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(
            timeout=self._timeout_seconds,
        )
        try:
            response = await client.post(
                KBO_DAY_GAMES_URL,
                data={
                    "leId": "1",
                    "srId": "0,1,3,4,5,6,7,8,9",
                    "date": game_date,
                },
                headers={
                    "Accept": "application/json, text/javascript, */*",
                    "Referer": (
                        "https://www.koreabaseball.com/"
                        "Schedule/GameCenter/Main.aspx"
                    ),
                    "User-Agent": "BaseballTour-MVP/0.1 status-sync",
                },
            )
            response.raise_for_status()
            data = response.json()
        finally:
            if owns_client:
                await client.aclose()

        if not isinstance(data, dict) or not isinstance(
            data.get("game"), list
        ):
            raise ValueError("KBO 일별 경기 응답 구조가 변경되었습니다.")
        return data
