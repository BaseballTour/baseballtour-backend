from datetime import datetime, timedelta, timezone
from typing import Any

from app.repositories.tour_api_cache_repository import TourApiCacheRepository


class FakeSnapshot:
    def __init__(self, data: dict[str, Any] | None) -> None:
        self._data = data
        self.exists = data is not None

    def to_dict(self) -> dict[str, Any] | None:
        return self._data


class FakeDocument:
    def __init__(self, store: dict[str, dict[str, Any]], key: str) -> None:
        self._store = store
        self._key = key

    def get(self) -> FakeSnapshot:
        return FakeSnapshot(self._store.get(self._key))

    def set(self, data: dict[str, Any]) -> None:
        self._store[self._key] = data


class FakeCollection:
    def __init__(self, store: dict[str, dict[str, Any]]) -> None:
        self._store = store

    def document(self, key: str) -> FakeDocument:
        return FakeDocument(self._store, key)


class FakeClient:
    def __init__(self) -> None:
        self.store: dict[str, dict[str, Any]] = {}

    def collection(self, name: str) -> FakeCollection:
        assert name == TourApiCacheRepository.COLLECTION_NAME
        return FakeCollection(self.store)


def test_cache_key_is_stable_and_does_not_contain_request_values() -> None:
    first = TourApiCacheRepository.cache_key(
        "searchKeyword2",
        {"keyword": "잠실", "pageNo": 1},
    )
    second = TourApiCacheRepository.cache_key(
        "searchKeyword2",
        {"pageNo": 1, "keyword": "잠실"},
    )

    assert first == second
    assert len(first) == 64
    assert "잠실" not in first


def test_set_and_get_valid_payload() -> None:
    client = FakeClient()
    repository = TourApiCacheRepository(client=client)  # type: ignore[arg-type]
    payload = {"response": {"header": {"resultCode": "0000"}}}

    repository.set("detailCommon2", {"contentId": "1"}, payload, ttl_seconds=60)

    assert repository.get("detailCommon2", {"contentId": "1"}) == payload


def test_get_ignores_expired_payload() -> None:
    client = FakeClient()
    repository = TourApiCacheRepository(client=client)  # type: ignore[arg-type]
    params = {"contentId": "1"}
    key = repository.cache_key("detailCommon2", params)
    client.store[key] = {
        "payload": {"response": {}},
        "expiresAt": datetime.now(timezone.utc) - timedelta(seconds=1),
    }

    assert repository.get("detailCommon2", params) is None
