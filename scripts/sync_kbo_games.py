import argparse
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.kbo_schedule_sync_service import KboScheduleSyncService


KOREA_TIMEZONE = ZoneInfo("Asia/Seoul")


def parse_args() -> argparse.Namespace:
    now = datetime.now(KOREA_TIMEZONE)
    parser = argparse.ArgumentParser(
        description="KBO 홈페이지 월별 일정을 Firestore games와 동기화합니다.",
    )
    parser.add_argument("--year", type=int, default=now.year)
    parser.add_argument("--month", type=int, default=now.month)
    parser.add_argument(
        "--write",
        action="store_true",
        help="지정할 때만 Firestore에 저장합니다. 기본값은 dry-run입니다.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    result = await KboScheduleSyncService().sync_month(
        args.year,
        args.month,
        dry_run=not args.write,
    )
    mode = "DRY-RUN" if result.dry_run else "WRITE"
    print(
        f"[{mode}] {args.year}-{args.month:02d}: "
        f"수집 {result.fetched}, 생성 {result.created}, 갱신 {result.updated}, "
        f"건너뜀 {len(result.skipped_rows)}"
    )
    for reason in result.skipped_rows:
        print(f"[건너뜀] {reason}")


if __name__ == "__main__":
    asyncio.run(main())
