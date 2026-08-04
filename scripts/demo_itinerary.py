import argparse
import asyncio
import json
from itertools import permutations
from pathlib import Path

from app.algorithms.itinerary_generator import generate_itinerary
from app.algorithms.travel_time import (
    TravelTimeMatrix,
    build_itinerary_travel_time_matrix,
)
from app.external.odsay.client import get_cached_transit_minutes
from app.models.itinerary import TripInput
from app.models.place import Place


ROOT = Path(__file__).resolve().parents[1]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live",
        action="store_true",
        help="ODsay 실제 대중교통 시간 사용",
    )
    args = parser.parse_args()
    trip = TripInput.model_validate_json(
        (ROOT / "samples/algorithm/trip_input.json").read_text(
            encoding="utf-8"
        )
    )
    places = [
        Place.model_validate(item)
        for item in json.loads(
            (ROOT / "samples/algorithm/places.json").read_text(
                encoding="utf-8"
            )
        )
    ]
    if args.live:
        matrix = await build_itinerary_travel_time_matrix(
            trip,
            places,
            get_cached_transit_minutes,
        )
    else:
        node_ids = [
            "arrival",
            "departure",
            "accommodation",
            "stadium",
            *(place.place_id for place in places),
        ]
        matrix = TravelTimeMatrix(
            minutes={pair: 15 for pair in permutations(node_ids, 2)}
        )
    result = generate_itinerary(trip, places, matrix)
    print(result.model_dump_json(by_alias=True, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
