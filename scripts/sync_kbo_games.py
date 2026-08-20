import argparse
import asyncio
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.services.kbo_schedule_sync_service import KboScheduleSyncService


KOREA_TIMEZONE = ZoneInfo("Asia/Seoul")


def parse_args() -> argparse.Namespace:
    now = datetime.now(KOREA_TIMEZONE)
    parser = argparse.ArgumentParser(
        description="KBO 홈페이지 월별 일정을 Firestore games와 동기화합니다.",
    )
    parser.add_argument("--year", type=int, default=now.year)
    parser.add_argument("--month", type=int)
    parser.add_argument(
        "--mode",
        choices=("schedule", "status"),
        default="schedule",
    )
    parser.add_argument(
        "--months-ahead",
        type=int,
        default=2,
        help="schedule 모드에서 현재 월 이후 추가로 동기화할 개월 수",
    )
    parser.add_argument(
        "--date",
        help="status 모드의 경기일(YYYY-MM-DD), 기본값은 한국 기준 오늘",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="지정할 때만 Firestore에 저장합니다. 기본값은 dry-run입니다.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    service = KboScheduleSyncService()
    if args.mode == "status":
        target_date = (
            date.fromisoformat(args.date)
            if args.date
            else datetime.now(KOREA_TIMEZONE).date()
        )
        result = await service.sync_day_status(
            target_date,
            dry_run=not args.write,
        )
        target_label = target_date.isoformat()
    elif args.month is not None:
        result = await service.sync_month(
            args.year,
            args.month,
            dry_run=not args.write,
        )
        target_label = f"{args.year}-{args.month:02d}"
    else:
        start_date = datetime.now(KOREA_TIMEZONE).date()
        result = await service.sync_horizon(
            start_date,
            months_ahead=args.months_ahead,
            dry_run=not args.write,
        )
        target_label = f"{start_date:%Y-%m} +{args.months_ahead}개월"
    mode = "DRY-RUN" if result.dry_run else "WRITE"
    print(
        f"[{mode}] {target_label}: "
        f"수집 {result.fetched}, 생성 {result.created}, 갱신 {result.updated}, "
        f"변경 없음 {result.unchanged}, "
        f"건너뜀 {len(result.skipped_rows)}"
    )
    for reason in result.skipped_rows:
        print(f"[건너뜀] {reason}")


if __name__ == "__main__":
    asyncio.run(main())
