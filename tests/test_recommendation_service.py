import asyncio
from unittest.mock import AsyncMock, Mock
from datetime import date

import pytest

from app.services import recommendation as recommendation_module
from app.external.tour_api.adapter import NearbyPlacePage
from app.models.place import (
    BusinessRuleStatus,
    Place,
    PlaceCategory,
    PlaceSource,
)
from app.services.recommendation import (
    ExcludedRecommendationPlace,
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
    **updates,
) -> Place:
    source_content_id = place_id.removeprefix("tour_")
    values = dict(
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
    values.update(updates)
    return Place(**values)


@pytest.mark.anyio
async def test_loads_multiple_recommendation_centers_in_parallel() -> None:
    started = 0
    both_started = asyncio.Event()

    async def load_page(**kwargs):
        nonlocal started
        started += 1
        if started == 2:
            both_started.set()
        await asyncio.wait_for(both_started.wait(), timeout=0.2)
        return NearbyPlacePage(places=[], next_page_token=None)

    adapter = Mock()
    adapter.get_nearby_place_page = AsyncMock(side_effect=load_page)
    adapter.get_place_detail = AsyncMock()

    result = await RecommendationService(adapter).get_candidates(
        centers=[
            RecommendationCenter(latitude=37.5, longitude=127.0),
            RecommendationCenter(latitude=37.6, longitude=127.1),
        ]
    )

    assert result == []
    assert adapter.get_nearby_place_page.await_count == 2


@pytest.mark.anyio
async def test_detail_timeout_keeps_nearby_candidate(monkeypatch) -> None:
    candidate = make_place("tour_slow_detail")
    adapter = Mock()
    adapter.get_nearby_place_page = AsyncMock(
        return_value=NearbyPlacePage(
            places=[candidate],
            next_page_token=None,
        )
    )

    async def slow_detail(content_id):
        await asyncio.sleep(0.05)
        return candidate

    adapter.get_place_detail = AsyncMock(side_effect=slow_detail)
    monkeypatch.setattr(
        recommendation_module,
        "DETAIL_TIMEOUT_SECONDS",
        0.01,
    )

    result = await RecommendationService(adapter).get_candidates(
        centers=[RecommendationCenter(latitude=37.5, longitude=127.0)]
    )

    assert [place.place_id for place in result] == ["tour_slow_detail"]


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
async def test_excludes_stadium_anchor_from_recommendations() -> None:
    stadium = make_place("tour_gocheok", distance=0)
    stadium.name = "고척 스카이돔"
    stadium.latitude = 37.4982
    stadium.longitude = 126.8671
    attraction = make_place("tour_attraction", distance=200)

    adapter = Mock()
    adapter.get_nearby_place_page = AsyncMock(
        return_value=NearbyPlacePage(
            places=[stadium, attraction],
            next_page_token=None,
        )
    )
    adapter.get_place_detail = AsyncMock(return_value=attraction)

    result = await RecommendationService(adapter).get_candidates(
        centers=[RecommendationCenter(latitude=37.4982, longitude=126.8671)],
        excluded_places=[
            ExcludedRecommendationPlace(
                name="고척스카이돔",
                latitude=37.4982,
                longitude=126.8671,
            )
        ],
    )

    assert [place.place_id for place in result] == ["tour_attraction"]


@pytest.mark.anyio
async def test_excludes_ve10_sports_facility() -> None:
    sports_complex = make_place(
        "tour_sports_complex",
        category=PlaceCategory.ACTIVITY,
        lcls_system2="VE10",
        lcls_system3="VE100100",
    )
    attraction = make_place("tour_attraction")
    adapter = Mock()
    adapter.get_nearby_place_page = AsyncMock(
        return_value=NearbyPlacePage(
            places=[sports_complex, attraction],
            next_page_token=None,
        )
    )
    adapter.get_place_detail = AsyncMock(return_value=attraction)

    diagnostics = {}
    result = await RecommendationService(adapter).get_candidates(
        centers=[RecommendationCenter(latitude=37.5, longitude=127.0)],
        diagnostics=diagnostics,
    )

    assert [place.place_id for place in result] == ["tour_attraction"]


@pytest.mark.anyio
async def test_excludes_festival_ended_before_trip() -> None:
    past_festival = make_place(
        "tour_past_festival",
        category=PlaceCategory.FESTIVAL,
        business_hours_status=BusinessRuleStatus.PARSED,
        event_start_date=date(2025, 8, 1),
        event_end_date=date(2025, 8, 3),
    )
    adapter = Mock()
    adapter.get_nearby_place_page = AsyncMock(
        return_value=NearbyPlacePage(
            places=[past_festival],
            next_page_token=None,
        )
    )
    adapter.get_place_detail = AsyncMock(return_value=past_festival)

    result = await RecommendationService(adapter).get_candidates(
        centers=[RecommendationCenter(latitude=36.3, longitude=127.4)],
        travel_start_date=date(2026, 8, 15),
        travel_end_date=date(2026, 8, 17),
    )

    assert result == []


@pytest.mark.anyio
async def test_caps_food_shopping_and_festival_candidates() -> None:
    candidates = [
        *(make_place(f"tour_restaurant_{index}", category=PlaceCategory.RESTAURANT, distance=index) for index in range(8)),
        *(make_place(f"tour_cafe_{index}", category=PlaceCategory.CAFE, distance=20 + index) for index in range(4)),
        *(make_place(f"tour_shopping_{index}", category=PlaceCategory.SHOPPING, distance=30 + index) for index in range(4)),
        *(make_place(f"tour_spot_{index}", distance=40 + index) for index in range(6)),
    ]
    adapter = Mock()
    adapter.get_nearby_place_page = AsyncMock(
        return_value=NearbyPlacePage(places=candidates, next_page_token=None)
    )
    adapter.get_place_detail = AsyncMock(
        side_effect=lambda content_id: next(
            item for item in candidates if item.source_content_id == content_id
        )
    )

    diagnostics = {}
    result = await RecommendationService(adapter).get_candidates(
        centers=[RecommendationCenter(latitude=37.5, longitude=127.0)],
        diagnostics=diagnostics,
    )

    assert sum(item.category == PlaceCategory.RESTAURANT for item in result) == 4
    assert sum(item.category == PlaceCategory.CAFE for item in result) == 2
    assert sum(item.category == PlaceCategory.SHOPPING for item in result) == 2
    assert sum(item.category == PlaceCategory.TOURIST_SPOT for item in result) == 4
    assert diagnostics["fetchedCount"] == len(candidates)
    assert diagnostics["candidateCount"] == len(result)
    assert diagnostics["filteredCounts"]["CANDIDATE_LIMIT"] > 0


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
async def test_all_nearby_centers_failed_raises_timeout() -> None:
    adapter = Mock()
    adapter.get_nearby_place_page = AsyncMock(
        side_effect=RuntimeError("TourAPI unavailable")
    )

    with pytest.raises(asyncio.TimeoutError):
        await RecommendationService(adapter).get_candidates(
            centers=[
                RecommendationCenter(latitude=35.19, longitude=129.06),
                RecommendationCenter(latitude=35.11, longitude=129.04),
            ]
        )


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

    assert len(result) == 12
    assert [place.distance_meters for place in result] == list(
        map(float, range(1, 13))
    )
    assert adapter.get_nearby_place_page.await_count == 2
    assert adapter.get_place_detail.await_count == 12


@pytest.mark.anyio
async def test_candidate_pool_reserves_restaurants_and_cafes() -> None:
    tourist_spots = [
        make_place(f"tour_spot_{index}", distance=float(index))
        for index in range(1, 17)
    ]
    dining = [
        make_place(
            "tour_restaurant_1",
            category=PlaceCategory.RESTAURANT,
            distance=100,
        ),
        make_place(
            "tour_restaurant_2",
            category=PlaceCategory.RESTAURANT,
            distance=110,
        ),
        make_place(
            "tour_cafe_1",
            category=PlaceCategory.CAFE,
            distance=120,
        ),
        make_place(
            "tour_cafe_2",
            category=PlaceCategory.CAFE,
            distance=130,
        ),
    ]
    places = [*tourist_spots, *dining]
    adapter = Mock()
    adapter.get_nearby_place_page = AsyncMock(
        return_value=NearbyPlacePage(places=places, next_page_token=None)
    )
    adapter.get_place_detail = AsyncMock(
        side_effect=lambda content_id: next(
            place
            for place in places
            if place.source_content_id == content_id
        )
    )

    result = await RecommendationService(
        adapter,
        max_candidates=10,
    ).get_candidates(
        centers=[RecommendationCenter(latitude=35.19, longitude=129.06)]
    )

    assert len(result) == 10
    assert sum(
        place.category == PlaceCategory.RESTAURANT for place in result
    ) == 2
    assert sum(place.category == PlaceCategory.CAFE for place in result) == 2


@pytest.mark.anyio
async def test_candidate_pool_reserves_fd03_breakfast_restaurant() -> None:
    places = [
        *[
            make_place(
                f"tour_restaurant_{index}",
                category=PlaceCategory.RESTAURANT,
                distance=float(index),
            )
            for index in range(1, 6)
        ],
        make_place(
            "tour_breakfast",
            category=PlaceCategory.RESTAURANT,
            distance=500,
            lcls_system2="FD03",
        ),
        *[
            make_place(f"tour_spot_{index}", distance=10 + index)
            for index in range(1, 10)
        ],
    ]
    adapter = Mock()
    adapter.get_nearby_place_page = AsyncMock(
        return_value=NearbyPlacePage(places=places, next_page_token=None)
    )
    adapter.get_place_detail = AsyncMock(
        side_effect=lambda content_id: next(
            place
            for place in places
            if place.source_content_id == content_id
        )
    )

    result = await RecommendationService(
        adapter,
        max_candidates=8,
    ).get_candidates(
        centers=[RecommendationCenter(latitude=35.19, longitude=129.06)]
    )

    assert any(place.lcls_system2 == "FD03" for place in result)
    assert sum(
        place.category == PlaceCategory.RESTAURANT for place in result
    ) >= 4


@pytest.mark.anyio
async def test_candidate_pool_round_robins_available_categories() -> None:
    places = [
        *[
            make_place(f"tour_spot_{index}", distance=float(index))
            for index in range(1, 10)
        ],
        make_place(
            "tour_culture",
            category=PlaceCategory.CULTURAL_FACILITY,
            distance=100,
        ),
        make_place(
            "tour_activity",
            category=PlaceCategory.ACTIVITY,
            distance=110,
        ),
        make_place(
            "tour_shopping",
            category=PlaceCategory.SHOPPING,
            distance=120,
        ),
    ]
    adapter = Mock()
    adapter.get_nearby_place_page = AsyncMock(
        return_value=NearbyPlacePage(places=places, next_page_token=None)
    )
    adapter.get_place_detail = AsyncMock(
        side_effect=lambda content_id: next(
            place for place in places if place.source_content_id == content_id
        )
    )
    diagnostics = {}

    result = await RecommendationService(adapter, max_candidates=6).get_candidates(
        centers=[RecommendationCenter(latitude=35.19, longitude=129.06)],
        diagnostics=diagnostics,
    )

    categories = {place.category for place in result}
    assert PlaceCategory.CULTURAL_FACILITY in categories
    assert PlaceCategory.ACTIVITY in categories
    assert PlaceCategory.SHOPPING in categories
    assert diagnostics["detailLookupCount"] == 6
    assert "CAFE" in diagnostics["missingSourceCategories"]
    assert diagnostics["businessHoursStatusDistribution"] == {"MISSING": 6}
