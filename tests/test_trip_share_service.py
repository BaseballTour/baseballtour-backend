from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.exceptions import AppException
from app.schemas.itinerary_plan import ItineraryPlanStatus
from app.schemas.trip import TripStatus
from app.services.trip_share_service import TripShareService


USER_ID = "owner_001"
TRIP_ID = "trip_001"
PLAN_ID = "plan_001"


def make_service(
    *,
    trip_status=TripStatus.GENERATED,
    active_plan_id=PLAN_ID,
    plan_status=ItineraryPlanStatus.ACTIVE,
    plan_exists=True,
):
    trip_service = Mock()
    trip_service.get_trip.return_value = SimpleNamespace(
        trip_id=TRIP_ID,
        user_id=USER_ID,
        status=trip_status,
        active_plan_id=active_plan_id,
    )

    plan_repository = Mock()
    plan_repository.get_by_id.return_value = (
        SimpleNamespace(
            plan_id=PLAN_ID,
            trip_id=TRIP_ID,
            user_id=USER_ID,
            status=plan_status,
        )
        if plan_exists
        else None
    )

    share_repository = Mock()
    share_repository.issue.return_value = "share-token"
    share_repository.revoke.return_value = True

    service = TripShareService(
        share_repository=share_repository,
        trip_service=trip_service,
        plan_repository=plan_repository,
    )
    return SimpleNamespace(
        service=service,
        trip_service=trip_service,
        plan_repository=plan_repository,
        share_repository=share_repository,
    )


def test_issue_uses_owned_trip_and_active_plan():
    context = make_service()

    token = context.service.issue(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    )

    assert token == "share-token"
    context.trip_service.get_trip.assert_called_once_with(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    )
    context.plan_repository.get_by_id.assert_called_once_with(PLAN_ID)
    context.share_repository.issue.assert_called_once_with(
        trip_id=TRIP_ID,
        user_id=USER_ID,
        expected_plan_id=PLAN_ID,
    )


@pytest.mark.parametrize(
    "trip_status,active_plan_id",
    [
        (TripStatus.PLANNING, None),
        (TripStatus.GENERATING, None),
        (TripStatus.CANCELLED, PLAN_ID),
    ],
)
def test_issue_rejects_unshareable_trip(
    trip_status,
    active_plan_id,
):
    context = make_service(
        trip_status=trip_status,
        active_plan_id=active_plan_id,
    )

    with pytest.raises(AppException) as exc_info:
        context.service.issue(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert exc_info.value.code == "TRIP_SHARE_NOT_AVAILABLE"
    context.share_repository.issue.assert_not_called()


@pytest.mark.parametrize(
    "plan_status,plan_exists",
    [
        (ItineraryPlanStatus.ARCHIVED, True),
        (ItineraryPlanStatus.ACTIVE, False),
    ],
)
def test_issue_rejects_missing_or_archived_plan(
    plan_status,
    plan_exists,
):
    context = make_service(
        plan_status=plan_status,
        plan_exists=plan_exists,
    )

    with pytest.raises(AppException) as exc_info:
        context.service.issue(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert exc_info.value.code == "TRIP_SHARE_NOT_AVAILABLE"
    context.share_repository.issue.assert_not_called()


def test_issue_allows_regeneration_with_active_plan():
    context = make_service(trip_status=TripStatus.GENERATING)

    assert context.service.issue(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    ) == "share-token"


def test_issue_rejects_state_changed_during_transaction():
    context = make_service()
    context.share_repository.issue.return_value = None

    with pytest.raises(AppException) as exc_info:
        context.service.issue(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert exc_info.value.code == "TRIP_SHARE_STATE_CHANGED"


def test_revoke_checks_owner_and_delegates():
    context = make_service()

    assert context.service.revoke(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    ) is True

    context.trip_service.get_trip.assert_called_once_with(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    )
    context.share_repository.revoke.assert_called_once_with(
        trip_id=TRIP_ID,
        user_id=USER_ID,
    )


def test_public_trip_rejects_unknown_token():
    context = make_service()
    context.share_repository.get_active_bundle.return_value = None

    with pytest.raises(AppException) as exc_info:
        context.service.get_public_trip(token="unknown-token")

    assert exc_info.value.code == "SHARE_NOT_FOUND"
    assert exc_info.value.status_code == 404


def test_issue_with_metadata_preserves_token_metadata():
    from unittest.mock import Mock

    from app.services.trip_share_service import TripShareService

    repository = Mock()
    created_at = datetime(
        2026, 9, 7, tzinfo=timezone.utc
    )
    repository.get_metadata.return_value = (created_at, None)

    service = TripShareService(
        share_repository=repository,
        trip_service=Mock(),
        plan_repository=Mock(),
        game_service=Mock(),
    )
    service.issue = Mock(return_value="first-token")

    result = service.issue_with_metadata(
        user_id="owner_001",
        trip_id="trip_001",
    )

    assert result == ("first-token", created_at, None)
    repository.get_metadata.assert_called_once_with(
        trip_id="trip_001",
        user_id="owner_001",
        token="first-token",
    )


def test_issue_with_metadata_rejects_changed_token():
    from unittest.mock import Mock

    from app.core.exceptions import AppException
    from app.services.trip_share_service import TripShareService

    repository = Mock()
    repository.get_metadata.return_value = None

    service = TripShareService(
        share_repository=repository,
        trip_service=Mock(),
        plan_repository=Mock(),
        game_service=Mock(),
    )
    service.issue = Mock(return_value="old-token")

    with pytest.raises(AppException) as captured:
        service.issue_with_metadata(
            user_id="owner_001",
            trip_id="trip_001",
        )

    assert captured.value.status_code == 409
    assert captured.value.code == "TRIP_SHARE_STATE_CHANGED"
