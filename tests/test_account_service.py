from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import status

from app.core.exceptions import AppException
from app.repositories.attendance_log_repository import (
    AttendanceLogRepository,
)
from app.repositories.favorite_collection_repository import (
    FavoriteCollectionRepository,
)
from app.repositories.itinerary_plan_repository import (
    ItineraryPlanRepository,
)
from app.repositories.place_selection_repository import (
    PlaceSelectionRepository,
)
from app.repositories.trip_repository import TripRepository
from app.repositories.user_repository import UserRepository
from app.services.account_service import AccountService
from app.services.storage_service import StorageService


def make_service(*, storage_service=None):
    user_repository = Mock(
        spec=UserRepository
    )
    trip_repository = Mock(
        spec=TripRepository
    )
    place_selection_repository = Mock(
        spec=PlaceSelectionRepository
    )
    itinerary_plan_repository = Mock(
        spec=ItineraryPlanRepository
    )
    favorite_collection_repository = Mock(
        spec=FavoriteCollectionRepository
    )
    attendance_log_repository = Mock(
        spec=AttendanceLogRepository
    )

    if storage_service is None:
        storage_service = Mock(
            spec=StorageService
        )

    service = AccountService(
        user_repository=user_repository,
        trip_repository=trip_repository,
        place_selection_repository=(
            place_selection_repository
        ),
        itinerary_plan_repository=(
            itinerary_plan_repository
        ),
        favorite_collection_repository=(
            favorite_collection_repository
        ),
        attendance_log_repository=(
            attendance_log_repository
        ),
        storage_service=storage_service,
    )

    return (
        service,
        user_repository,
        trip_repository,
        place_selection_repository,
        itinerary_plan_repository,
        favorite_collection_repository,
        attendance_log_repository,
    )


def test_withdraw_user_cleans_owned_data() -> None:
    (
        service,
        user_repository,
        trip_repository,
        place_selection_repository,
        itinerary_plan_repository,
        favorite_collection_repository,
        attendance_log_repository,
    ) = make_service()

    trip_repository.get_by_user_id.return_value = [
        SimpleNamespace(trip_id="trip-1"),
        SimpleNamespace(trip_id="trip-2"),
    ]
    user_repository.soft_delete.return_value = True

    service.withdraw_user(
        user_id="user-001"
    )

    assert (
        place_selection_repository.delete_all.call_count
        == 2
    )
    assert (
        itinerary_plan_repository.delete_all_by_trip_id.call_count
        == 2
    )

    assert trip_repository.delete.call_count == 2

    favorite_collection_repository.delete_all_by_user_id.assert_called_once_with(
        user_id="user-001"
    )

    attendance_log_repository.soft_delete_all_by_user_id.assert_called_once()

    arguments = (
        attendance_log_repository
        .soft_delete_all_by_user_id
        .call_args
    )

    assert arguments.args[0] == "user-001"
    assert "deleted_at" in arguments.kwargs

    user_repository.soft_delete.assert_called_once()

    user_arguments = (
        user_repository.soft_delete.call_args
    )

    assert user_arguments.args[0] == "user-001"
    assert "deleted_at" in user_arguments.kwargs


def test_withdraw_user_does_not_delete_user_when_cleanup_fails() -> None:
    (
        service,
        user_repository,
        trip_repository,
        place_selection_repository,
        itinerary_plan_repository,
        favorite_collection_repository,
        attendance_log_repository,
    ) = make_service()

    trip_repository.get_by_user_id.return_value = [
        SimpleNamespace(trip_id="trip-1"),
    ]

    place_selection_repository.delete_all.side_effect = (
        RuntimeError("cleanup failed")
    )

    with pytest.raises(RuntimeError):
        service.withdraw_user(
            user_id="user-001"
        )

    user_repository.soft_delete.assert_not_called()

    favorite_collection_repository.delete_all_by_user_id.assert_not_called()
    attendance_log_repository.soft_delete_all_by_user_id.assert_not_called()


def test_withdraw_user_rejects_missing_user() -> None:
    (
        service,
        user_repository,
        trip_repository,
        place_selection_repository,
        itinerary_plan_repository,
        favorite_collection_repository,
        attendance_log_repository,
    ) = make_service()

    trip_repository.get_by_user_id.return_value = []
    user_repository.soft_delete.return_value = False

    with pytest.raises(AppException) as exc_info:
        service.withdraw_user(
            user_id="user-001"
        )

    assert (
        exc_info.value.status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert exc_info.value.code == "USER_NOT_FOUND"


def test_withdraw_user_does_not_delete_user_when_favorite_cleanup_fails() -> None:
    (
        service,
        user_repository,
        trip_repository,
        place_selection_repository,
        itinerary_plan_repository,
        favorite_collection_repository,
        attendance_log_repository,
    ) = make_service()

    trip_repository.get_by_user_id.return_value = []

    favorite_collection_repository.delete_all_by_user_id.side_effect = (
        RuntimeError("favorite cleanup failed")
    )

    with pytest.raises(RuntimeError):
        service.withdraw_user(
            user_id="user-001"
        )

    favorite_collection_repository.delete_all_by_user_id.assert_called_once_with(
        user_id="user-001"
    )

    attendance_log_repository.soft_delete_all_by_user_id.assert_not_called()
    user_repository.soft_delete.assert_not_called()


def test_withdraw_user_cleans_storage_files() -> None:
    storage_service = Mock(
        spec=StorageService
    )

    (
        service,
        user_repository,
        trip_repository,
        _,
        _,
        _,
        _,
    ) = make_service(
        storage_service=storage_service
    )

    trip_repository.get_by_user_id.return_value = []
    user_repository.soft_delete.return_value = True

    service.withdraw_user(
        user_id="user-001"
    )

    storage_service.delete_user_files.assert_called_once_with(
        "user-001"
    )


def test_withdraw_user_stops_before_firestore_when_storage_fails() -> None:
    storage_service = Mock(
        spec=StorageService
    )

    storage_service.delete_user_files.side_effect = (
        RuntimeError("storage cleanup failed")
    )

    (
        service,
        user_repository,
        trip_repository,
        place_selection_repository,
        itinerary_plan_repository,
        favorite_collection_repository,
        attendance_log_repository,
    ) = make_service(
        storage_service=storage_service
    )

    with pytest.raises(
        RuntimeError,
        match="storage cleanup failed",
    ):
        service.withdraw_user(
            user_id="user-001"
        )

    trip_repository.get_by_user_id.assert_not_called()
    place_selection_repository.delete_all.assert_not_called()
    itinerary_plan_repository.delete_all_by_trip_id.assert_not_called()
    favorite_collection_repository.delete_all_by_user_id.assert_not_called()
    attendance_log_repository.soft_delete_all_by_user_id.assert_not_called()
    user_repository.soft_delete.assert_not_called()
