from fastapi.testclient import TestClient

from app.api.v1.endpoints import tour as tour_endpoint
from app.external.tour_api.adapter import NearbyPlacePage
from app.external.tour_api.filters import TourFilterId
from app.main import app


client = TestClient(app)


def test_search_forwards_new_classification_filters(monkeypatch) -> None:
    received: dict[str, object] = {}

    async def fake_search_place_page(**kwargs) -> NearbyPlacePage:
        received.update(kwargs)
        return NearbyPlacePage([], None)

    monkeypatch.setattr(
        tour_endpoint.tour_api_adapter,
        "search_place_page",
        fake_search_place_page,
    )

    response = client.get(
        "/api/v1/tour/search",
        params={
            "keyword": "서울 맛집",
            "lclsSystem1": "FD",
            "lclsSystem2": "FD02",
            "lclsSystem3": "FD020200",
        },
    )

    assert response.status_code == 200
    assert received["lcls_system1"] == "FD"
    assert received["lcls_system2"] == "FD02"
    assert received["lcls_system3"] == "FD020200"


def test_search_requires_parent_classification_codes() -> None:
    response = client.get(
        "/api/v1/tour/search",
        params={
            "keyword": "서울 맛집",
            "lclsSystem3": "FD020200",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == (
        "INVALID_CLASSIFICATION_FILTER"
    )


def test_search_rejects_malformed_classification_code() -> None:
    response = client.get(
        "/api/v1/tour/search",
        params={
            "keyword": "서울 맛집",
            "lclsSystem1": "food",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_search_forwards_frontend_filter_id(monkeypatch) -> None:
    received: dict[str, object] = {}

    async def fake_search_place_page_by_filter(**kwargs) -> NearbyPlacePage:
        received.update(kwargs)
        return NearbyPlacePage([], None)

    monkeypatch.setattr(
        tour_endpoint.tour_api_adapter,
        "search_place_page_by_filter",
        fake_search_place_page_by_filter,
    )
    response = client.get(
        "/api/v1/tour/search",
        params={"keyword": "초밥", "filterId": "JAPANESE"},
    )
    assert response.status_code == 200
    assert received["filter_id"] == TourFilterId.JAPANESE


def test_search_rejects_filter_id_and_raw_codes_together() -> None:
    response = client.get(
        "/api/v1/tour/search",
        params={
            "keyword": "카페",
            "filterId": "CAFE",
            "lclsSystem1": "FD",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "FILTER_CONFLICT"


def test_filter_options_exposes_compound_fishing_codes() -> None:
    response = client.get("/api/v1/tour/filter-options")
    assert response.status_code == 200
    fishing = next(
        item for item in response.json()["data"] if item["filterId"] == "FISHING"
    )
    assert fishing["classificationCodes"] == ["LS020500", "LS020600"]
