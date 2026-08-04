import json
from itertools import permutations
from pathlib import Path

from app.algorithms.itinerary_generator import generate_itinerary
from app.algorithms.travel_time import TravelTimeMatrix
from app.models.itinerary import TripInput
from app.models.place import Place


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
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
    main()
