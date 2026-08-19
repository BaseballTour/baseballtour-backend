from unittest.mock import AsyncMock, Mock

import pytest

from app.external.tour_api.adapter import NearbyPlacePage
from app.models.place import (
    BusinessRuleStatus,
    Place,
    PlaceCategory,
    PlaceSource,
)
from app.services.recommendation import (
    RecommendationCenter,
    RecommendationService,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def make_place(
    place_id: str,
    *,
    category: PlaceCategory = PlaceCategory.TOURIST_SPOT,
    distance: float | None = 100,
    source: PlaceSource = PlaceSource.TOUR_API,
    business_hours_status: BusinessRuleStatus = BusinessRuleStatus.MISSING,
) -> Place:
    source_content_id = place_id.removeprefix("tour_")
    return Place(
        place_id=place_id,
        name=place_id,
        category=category,
        latitude=35.19,
        longitude=129.06,
        distance_meters=distance,
        source=source,
        source_content_id=source_content_id,
        business_hours_status=business_hours_status,
    )


@pytest.mark.anyio
async def test_returns_only_unique_unselected_tour_api_candidates() -> None:
    selected = make_place("tour_selected")
    nearest = make_place("tour_duplicate", distance=80)
    farther = make_place("tour_duplicate", distance=300)
    accommodation = make_place(
        "tour_hotel",
        category=PlaceCategory.ACCOMMODATION,
    )
    kakao = make_place(
        "kakao_place",
        source=PlaceSource.KAKAO,
    )
    restaurant = make_place(
        "tour_restaurant",
        category=PlaceCategory.RESTAURANT,
        distance=150,
    )

    adapter = Mock()
    adapter.get_nearby_place_page = AsyncMock(
        side_effect=[
            NearbyPlacePage(
                places=[selected, farther, accommodation, kakao],
                next_page_token="2",
            ),
            NearbyPlacePage(
                places=[nearest, restaurant],
                next_page_token=None,
            ),
        ]
    )
    adapter.get_place_detail = AsyncMock(
        side_effect=lambda content_id: {
            "duplicate": nearest,
            "restaurant": restaurant,
        }[content_id]
    )

    service = RecommendationService(
        adapter,
        radius=5000,
        page_size=20,
        max_pages_per_center=2,
    )
    result = await service.get_candidates(
        centers=[RecommendationCenter(latitude=35.19, longitude=129.06)],
        selected_place_ids=[selected.place_id],
    )

    assert [place.place_id for place in result] == [
        "tour_duplicate",
        "tour_restaurant",
    ]
    assert result[0].distance_meters == 80
    assert adapter.get_nearby_place_page.await_count == 2
    assert adapter.get_nearby_place_page.await_args_list[0].kwargs == {
        "longitude": 129.06,
        "latitude": 35.19,
        "radius": 5000,
        "page_no": 1,
        "num_of_rows": 20,
    }


@pytest.mark.anyio
async def test_excludes_festival_without_parsed_operating_rules() -> None:
    festival = make_place(
        "tour_festival",
        category=PlaceCategory.FESTIVAL,
    )
    parsed_festival = festival.model_copy(
        update={"business_hours_status": BusinessRuleStatus.PARSED}
    )

    adapter = Mock()
    adapter.get_nearby_place_page = AsyncMock(
        return_value=NearbyPlacePage(
            places=[festival],
            next_page_token=None,
        )
    )
    adapter.get_place_detail = AsyncMock(return_value=parsed_festival)

    result = await RecommendationService(adapter).get_candidates(
        centers=[RecommendationCenter(latitude=35.19, longitude=129.06)]
    )

    assert [place.place_id for place in result] == ["tour_festival"]

    adapter.get_place_detail.return_value = festival
    result = await RecommendationService(adapter).get_candidates(
        centers=[RecommendationCenter(latitude=35.19, longitude=129.06)]
    )

    assert result == []


@pytest.mark.anyio
async def test_nearby_or_detail_failure_does_not_fail_recommendation() -> None:
    fallback = make_place("tour_fallback")
    adapter = Mock()
    adapter.get_nearby_place_page = AsyncMock(
        side_effect=[
            NearbyPlacePage(places=[fallback], next_page_token=None),
            RuntimeError("TourAPI unavailable"),
        ]
    )
    adapter.get_place_detail = AsyncMock(
        side_effect=RuntimeError("detail unavailable")
    )

    result = await RecommendationService(adapter).get_candidates(
        centers=[
            RecommendationCenter(latitude=35.19, longitude=129.06),
            RecommendationCenter(latitude=35.11, longitude=129.04),
        ]
    )

    assert result == [fallback]


@pytest.mark.anyio
async def test_duplicate_centers_are_queried_once() -> None:
    adapter = Mock()
    adapter.get_nearby_place_page = AsyncMock(
        return_value=NearbyPlacePage(places=[], next_page_token=None)
    )

    await RecommendationService(adapter).get_candidates(
        centers=[
            RecommendationCenter(latitude=35.19, longitude=129.06),
            RecommendationCenter(latitude=35.1900001, longitude=129.0600001),
        ]
    )

    adapter.get_nearby_place_page.assert_awaited_once()


@pytest.mark.anyio
async def test_default_candidate_pool_is_limited_before_detail_lookup() -> None:
    places = [
        make_place(f"tour_{index}", distance=float(index))
        for index in range(20, 0, -1)
    ]
    adapter = Mock()
    adapter.get_nearby_place_page = AsyncMock(
        return_value=NearbyPlacePage(
            places=places,
            next_page_token="2",
        )
    )
    adapter.get_place_detail = AsyncMock(
        side_effect=lambda content_id: next(
            place
            for place in places
            if place.source_content_id == content_id
        )
    )

    result = await RecommendationService(adapter).get_candidates(
        centers=[RecommendationCenter(latitude=35.19, longitude=129.06)]
    )

    assert len(result) == 15
    assert [place.distance_meters for place in result] == list(
        map(float, range(1, 16))
    )
    assert adapter.get_nearby_place_page.await_count == 1
    assert adapter.get_place_detail.await_count == 15
