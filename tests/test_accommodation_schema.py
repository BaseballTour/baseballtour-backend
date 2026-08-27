from app.schemas.trip import AccommodationInfo


def test_accommodation_preserves_kakao_place_id() -> None:
    accommodation = AccommodationInfo.model_validate(
        {
            "name": "고척 스테이 호텔",
            "address": "서울 구로구 경인로 430",
            "latitude": 37.4982,
            "longitude": 126.8671,
            "kakaoPlaceId": "12345",
        }
    )

    assert accommodation.kakao_place_id == "12345"
    assert accommodation.model_dump(mode="json", by_alias=True)[
        "kakaoPlaceId"
    ] == "12345"
