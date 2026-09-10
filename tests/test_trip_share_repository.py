from datetime import datetime, timezone
from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import app.repositories.trip_share_repository as share_module
from app.repositories.trip_share_repository import TripShareRepository


TRIP_ID = "trip_001"
OWNER_ID = "owner_001"
OTHER_ID = "other_001"


def token_hash(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


class FakeDocument:
    def __init__(self, store, path):
        self.store = store
        self.path = path

    def get(self, transaction=None):
        data = self.store.records.get(self.path)
        return SimpleNamespace(
            exists=data is not None,
            to_dict=lambda: deepcopy(data),
        )


class FakeCollection:
    def __init__(self, store, name):
        self.store = store
        self.name = name

    def document(self, document_id):
        return FakeDocument(
            self.store,
            f"{self.name}/{document_id}",
        )


class FakeTransaction:
    def __init__(self, store):
        self.store = store
        self.operations = []

    def set(self, reference, data):
        self.operations.append(
            ("set", reference.path, deepcopy(data))
        )

    def update(self, reference, data):
        self.operations.append(
            ("update", reference.path, deepcopy(data))
        )

    def delete(self, reference):
        self.operations.append(
            ("delete", reference.path, None)
        )

    def commit(self):
        # 성공한 트랜잭션의 쓰기만 한꺼번에 반영합니다.
        records = deepcopy(self.store.records)

        for operation, path, data in self.operations:
            if operation == "set":
                records[path] = data
            elif operation == "update":
                if path not in records:
                    raise KeyError(path)
                records[path].update(data)
            elif operation == "delete":
                records.pop(path, None)

        self.store.records = records


class FakeStore:
    def __init__(self):
        self.records = {}
        self.client = Mock()
        self.client.collection.side_effect = (
            lambda name: FakeCollection(self, name)
        )
        self.client.transaction.side_effect = (
            lambda: FakeTransaction(self)
        )


def bypass_transactional(function):
    """Firestore 없이 성공한 트랜잭션의 쓰기를 반영합니다."""
    def run(transaction):
        result = function(transaction)
        transaction.commit()
        return result

    return run


@pytest.fixture
def context(monkeypatch):
    store = FakeStore()
    store.records[f"trips/{TRIP_ID}"] = {
        "userId": OWNER_ID,
    }

    monkeypatch.setattr(
        share_module,
        "transactional",
        bypass_transactional,
    )

    repository = TripShareRepository(client=store.client)
    return SimpleNamespace(repository=repository, store=store)


def test_issue_creates_hashed_token_index(context, monkeypatch):
    def generate_token(n):
        assert n == 32
        return "first-token"

    monkeypatch.setattr(
        share_module.secrets,
        "token_urlsafe",
        generate_token,
    )

    token = context.repository.issue(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
    )

    assert token == "first-token"

    share = context.store.records[f"tripShares/{TRIP_ID}"]
    index = context.store.records[
        f"tripShareTokens/{token_hash(token)}"
    ]

    assert share["token"] == token
    assert share["tokenHash"] == token_hash(token)
    assert share["isActive"] is True
    assert index["tripId"] == TRIP_ID
    assert index["isActive"] is True
    assert token not in index.values()


def test_issue_returns_same_active_token(context, monkeypatch):
    generator = Mock(side_effect=["first-token", "second-token"])
    monkeypatch.setattr(
        share_module.secrets,
        "token_urlsafe",
        generator,
    )

    first = context.repository.issue(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
    )
    second = context.repository.issue(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
    )

    assert first == second == "first-token"
    generator.assert_called_once_with(32)


def test_revoke_disables_old_token(context, monkeypatch):
    monkeypatch.setattr(
        share_module.secrets,
        "token_urlsafe",
        lambda n: "first-token",
    )

    token = context.repository.issue(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
    )

    assert context.repository.get_active_trip_id(token) == TRIP_ID

    assert context.repository.revoke(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
    ) is True

    share = context.store.records[f"tripShares/{TRIP_ID}"]

    assert share["isActive"] is False
    assert share["token"] is None
    assert share["revokedAt"] is not None
    assert f"tripShareTokens/{token_hash(token)}" not in (
        context.store.records
    )
    assert context.repository.get_active_trip_id(token) is None

    # 이미 해제된 공유를 다시 해제해도 안전합니다.
    assert context.repository.revoke(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
    ) is False


def test_reissue_creates_new_token(context, monkeypatch):
    monkeypatch.setattr(
        share_module.secrets,
        "token_urlsafe",
        Mock(side_effect=["first-token", "second-token"]),
    )

    first = context.repository.issue(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
    )
    context.repository.revoke(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
    )
    second = context.repository.issue(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
    )

    assert first != second
    assert context.repository.get_active_trip_id(first) is None
    assert context.repository.get_active_trip_id(second) == TRIP_ID


@pytest.mark.parametrize(
    "trip_exists,user_id",
    [
        (False, OWNER_ID),
        (True, OTHER_ID),
    ],
)
def test_missing_trip_or_wrong_owner_cannot_issue_or_revoke(
    context,
    trip_exists,
    user_id,
):
    if not trip_exists:
        context.store.records.pop(f"trips/{TRIP_ID}")

    assert context.repository.issue(
        trip_id=TRIP_ID,
        user_id=user_id,
    ) is None

    assert context.repository.revoke(
        trip_id=TRIP_ID,
        user_id=user_id,
    ) is False

    assert f"tripShares/{TRIP_ID}" not in context.store.records


def test_unknown_or_mismatched_token_is_rejected(context, monkeypatch):
    monkeypatch.setattr(
        share_module.secrets,
        "token_urlsafe",
        lambda n: "first-token",
    )

    token = context.repository.issue(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
    )

    assert context.repository.get_active_trip_id("unknown") is None

    context.store.records[f"tripShares/{TRIP_ID}"][
        "tokenHash"
    ] = token_hash("another-token")

    assert context.repository.get_active_trip_id(token) is None


def test_issue_reuses_winner_on_transaction_retry(
    context,
    monkeypatch,
):
    """첫 시도가 충돌로 폐기되고 재시도한 상황을 모의합니다."""
    generator = Mock(return_value="losing-token")
    monkeypatch.setattr(
        share_module.secrets,
        "token_urlsafe",
        generator,
    )

    winning_token = "winning-token"

    def simulate_retry(function):
        def run(transaction):
            # 첫 시도는 쓰기를 준비하지만 커밋하지 않습니다.
            function(transaction)

            # 그 사이 다른 요청이 공유 발급에 성공한 상황입니다.
            context.store.records[f"tripShares/{TRIP_ID}"] = {
                "tripId": TRIP_ID,
                "userId": OWNER_ID,
                "token": winning_token,
                "tokenHash": token_hash(winning_token),
                "isActive": True,
            }
            context.store.records[
                f"tripShareTokens/{token_hash(winning_token)}"
            ] = {
                "tripId": TRIP_ID,
                "isActive": True,
            }

            # Firestore가 콜백을 재실행한 상황을 모의합니다.
            retry_transaction = context.store.client.transaction()
            result = function(retry_transaction)
            retry_transaction.commit()
            return result

        return run

    monkeypatch.setattr(
        share_module,
        "transactional",
        simulate_retry,
    )

    token = context.repository.issue(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
    )

    assert token == winning_token
    generator.assert_called_once_with(32)
    assert f"tripShareTokens/{token_hash('losing-token')}" not in (
        context.store.records
    )


def test_deleted_trip_cannot_be_resolved(context, monkeypatch):
    """여행이 삭제되면 기존 공유 토큰으로 공개 조회할 수 없습니다."""
    monkeypatch.setattr(
        share_module.secrets,
        "token_urlsafe",
        lambda n: "first-token",
    )

    token = context.repository.issue(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
    )

    context.store.records.pop(f"trips/{TRIP_ID}")

    assert context.repository.get_active_bundle(token) is None


def test_active_bundle_reads_current_trip_and_plan(context, monkeypatch):
    """유효한 공유만 현재 활성 여행과 Plan을 반환합니다."""
    from datetime import datetime, timedelta, timezone
    from app.schemas.trip import TripRecord, TripStatus
    from app.schemas.itinerary_plan import (
        ItineraryPlanRecord,
        ItineraryPlanStatus,
    )

    now = datetime(2026, 8, 15, 3, 0, tzinfo=timezone.utc)
    plan_id = "plan_001"

    trip = TripRecord(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
        game_id="game_001",
        title="부산 원정",
        trip_start_at=now,
        trip_end_at=now + timedelta(days=1),
        status=TripStatus.GENERATED,
        active_plan_id=plan_id,
        created_at=now,
        updated_at=now,
    )
    plan = ItineraryPlanRecord(
        plan_id=plan_id,
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
        status=ItineraryPlanStatus.ACTIVE,
        algorithm_version="test",
        total_travel_minutes=0,
        days=[],
        excluded_places=[],
        created_at=now,
        updated_at=now,
    )

    trip_data = trip.model_dump(
        by_alias=True,
        exclude_none=False,
    )
    trip_data.pop("tripId", None)
    context.store.records[f"trips/{TRIP_ID}"] = trip_data

    plan_data = plan.model_dump(
        by_alias=True,
        exclude_none=False,
    )
    plan_data.pop("planId", None)
    context.store.records[f"itineraryPlans/{plan_id}"] = plan_data

    monkeypatch.setattr(
        share_module.secrets,
        "token_urlsafe",
        lambda n: "first-token",
    )
    token = context.repository.issue(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
        expected_plan_id=plan_id,
    )

    bundle = context.repository.get_active_bundle(token)
    assert bundle is not None
    assert bundle[0].trip_id == TRIP_ID
    assert bundle[1].plan_id == plan_id

    context.store.records[f"itineraryPlans/{plan_id}"]["status"] = "ARCHIVED"
    assert context.repository.get_active_bundle(token) is None

    context.store.records[f"itineraryPlans/{plan_id}"]["status"] = "ACTIVE"
    context.store.records[f"trips/{TRIP_ID}"]["status"] = "CANCELLED"
    assert context.repository.get_active_bundle(token) is None


def test_trip_repository_delete_removes_share_index(context, monkeypatch):
    """기존 여행 삭제 API의 Repository 경로에서 공유도 정리합니다."""
    from app.repositories.trip_repository import TripRepository

    monkeypatch.setattr(
        share_module.secrets,
        "token_urlsafe",
        lambda n: "first-token",
    )
    token = context.repository.issue(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
    )

    TripRepository(client=context.store.client).delete(TRIP_ID)

    assert f"trips/{TRIP_ID}" not in context.store.records
    assert f"tripShares/{TRIP_ID}" not in context.store.records
    assert f"tripShareTokens/{token_hash(token)}" not in context.store.records
    assert context.repository.get_active_bundle(token) is None


def test_trip_delete_failed_commit_preserves_all_documents(
    context,
    monkeypatch,
):
    """커밋 실패를 모의하면 여행과 공유 정보가 모두 유지됩니다."""
    from copy import deepcopy
    from app.repositories.trip_repository import TripRepository

    monkeypatch.setattr(
        share_module.secrets,
        "token_urlsafe",
        lambda n: "first-token",
    )
    context.repository.issue(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
    )
    before = deepcopy(context.store.records)

    def fail_commit(self):
        raise RuntimeError("simulated commit failure")

    monkeypatch.setattr(FakeTransaction, "commit", fail_commit)

    with pytest.raises(RuntimeError, match="simulated commit failure"):
        TripRepository(client=context.store.client).delete(TRIP_ID)

    assert context.store.records == before


def test_issue_metadata_matches_active_token(context, monkeypatch):
    generator = Mock(side_effect=["first-token", "second-token"])
    monkeypatch.setattr(
        share_module.secrets,
        "token_urlsafe",
        generator,
    )

    first = context.repository.issue(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
    )
    metadata = context.repository.get_metadata(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
        token=first,
    )

    assert metadata is not None
    created_at, revoked_at = metadata
    assert isinstance(created_at, datetime)
    assert created_at.tzinfo is not None
    assert revoked_at is None

    assert context.repository.issue(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
    ) == first
    assert context.repository.get_metadata(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
        token=first,
    ) == metadata

    assert context.repository.get_metadata(
        trip_id=TRIP_ID,
        user_id=OTHER_ID,
        token=first,
    ) is None
    assert context.repository.get_metadata(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
        token="different-token",
    ) is None

    assert context.repository.revoke(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
    ) is True
    assert context.repository.get_metadata(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
        token=first,
    ) is None

    second = context.repository.issue(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
    )
    assert second != first
    assert context.repository.get_metadata(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
        token=first,
    ) is None
    assert context.repository.get_metadata(
        trip_id=TRIP_ID,
        user_id=OWNER_ID,
        token=second,
    ) is not None
