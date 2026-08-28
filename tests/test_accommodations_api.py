from fastapi.testclient import TestClient

from app.api.v1.endpoints import accommodations as endpoint
from app.external.kakao.client import KakaoPlacePage
from app.main import app


client = TestClient(app)


def kakao_hotel() -> dict:
    return {
        "id": "12345",
        "place_name": "고척 스테이 호텔",
        "category_group_code": "AD5",
        "category_name": "여행 > 숙박 > 호텔",
        "phone": "02-123-4567",
        "address_name": "서울 구로구 고척동 1",
        "road_address_name": "서울 구로구 경인로 430",
        "x": "126.8671",
        "y": "37.4982",
        "place_url": "https://place.map.kakao.com/12345",
    }


def test_search_accommodations_uses_kakao_lodging_category(monkeypatch) -> None:
    received = {}

    async def fake_search(query, **kwargs):
        received["query"] = query
        received.update(kwargs)
        return KakaoPlacePage(documents=[kakao_hotel()], is_end=False)

    monkeypatch.setattr(endpoint, "search_place_page", fake_search)

    response = client.get(
        "/api/v1/accommodations/search",
        params={
            "keyword": "고척 호텔",
            "longitude": 126.8671,
            "latitude": 37.4982,
        },
    )

    assert response.status_code == 200
    assert received["category_group_code"] == "AD5"
    assert received["query"] == "고척 호텔"
    body = response.json()
    assert body["data"][0] == {
        "kakaoPlaceId": "12345",
        "name": "고척 스테이 호텔",
        "address": "서울 구로구 경인로 430",
        "roadAddressName": "서울 구로구 경인로 430",
        "latitude": 37.4982,
        "longitude": 126.8671,
        "phone": "02-123-4567",
        "placeUrl": "https://place.map.kakao.com/12345",
        "categoryName": "여행 > 숙박 > 호텔",
        "selectionType": "KAKAO_PLACE",
    }
    assert body["meta"]["nextPageToken"] == "2"


def test_accommodation_search_openapi_uses_page_size_15() -> None:
    operation = app.openapi()["paths"][
        "/api/v1/accommodations/search"
    ]["get"]
    parameter = next(
        item
        for item in operation["parameters"]
        if item["name"] == "pageSize"
    )

    assert parameter["schema"]["default"] == 15
    assert parameter["schema"]["maximum"] == 15
    assert parameter["example"] == 15


def test_search_requires_coordinate_pair() -> None:
    response = client.get(
        "/api/v1/accommodations/search",
        params={"keyword": "호텔", "latitude": 37.5},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == (
        "ACCOMMODATION_COORDINATES_INCOMPLETE"
    )


def test_reverse_geocode_builds_map_point_candidate(monkeypatch) -> None:
    async def fake_reverse(**kwargs):
        return [
            {
                "road_address": {
                    "address_name": "서울 구로구 경인로 430",
                    "building_name": "사용자 선택 숙소",
                },
                "address": {"address_name": "서울 구로구 고척동 1"},
            }
        ]

    monkeypatch.setattr(endpoint, "reverse_geocode", fake_reverse)
    response = client.get(
        "/api/v1/accommodations/reverse-geocode",
        params={"longitude": 126.8671, "latitude": 37.4982},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["kakaoPlaceId"] is None
    assert data["name"] == "사용자 선택 숙소"
    assert data["address"] == "서울 구로구 경인로 430"
    assert data["selectionType"] == "MAP_POINT"


def test_reverse_geocode_returns_not_found_for_empty_result(monkeypatch) -> None:
    async def fake_reverse(**kwargs):
        return []

    monkeypatch.setattr(endpoint, "reverse_geocode", fake_reverse)
    response = client.get(
        "/api/v1/accommodations/reverse-geocode",
        params={"longitude": 126.8671, "latitude": 37.4982},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == (
        "ACCOMMODATION_ADDRESS_NOT_FOUND"
    )
