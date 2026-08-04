import asyncio

from app.external.odsay.client import get_transit_minutes


async def main() -> None:
    try:
        minutes = await get_transit_minutes(
            origin_longitude=127.0719,
            origin_latitude=37.5122,
            destination_longitude=126.8671,
            destination_latitude=37.4982,
        )
    except Exception as exc:
        print(f"ODSAY_CHECK_FAILED={type(exc).__name__}")
        return

    print("ODSAY_CHECK_OK=True")
    print(f"TRANSIT_MINUTES={minutes}")


if __name__ == "__main__":
    asyncio.run(main())
