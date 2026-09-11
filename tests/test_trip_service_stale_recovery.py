from types import SimpleNamespace

from app.services.trip_service import TripService, TripStatus


def make_service(repository):
    service = TripService.__new__(TripService)
    service._trip_repository = repository
    return service


def test_non_generating_trip_does_not_run_recovery():
    trip = SimpleNamespace(
        trip_id="trip_001",
        user_id="user_001",
        status=TripStatus.GENERATED,
        active_plan_id="plan_001",
    )

    class Repository:
        def recover_stale_generation(self, **kwargs):
            raise AssertionError("recovery must not run")

    service = make_service(Repository())

    assert service._recover_stale_generation(trip) is trip


def test_generating_trip_runs_stale_recovery():
    stale = SimpleNamespace(
        trip_id="trip_001",
        user_id="user_001",
        status=TripStatus.GENERATING,
        active_plan_id="plan_001",
    )

    recovered = SimpleNamespace(
        trip_id="trip_001",
        user_id="user_001",
        status=TripStatus.GENERATED,
        active_plan_id="plan_001",
    )

    calls = []

    class Repository:
        def recover_stale_generation(self, **kwargs):
            calls.append(kwargs)
            return recovered

    service = make_service(Repository())

    result = service._recover_stale_generation(stale)

    assert result is recovered
    assert len(calls) == 1
    assert calls[0]["trip_id"] == "trip_001"
    assert calls[0]["stale_before"] < calls[0]["updated_at"]


def test_get_my_trips_recovers_stale_generating_trip():
    stale = SimpleNamespace(
        trip_id="trip_001",
        user_id="user_001",
        status=TripStatus.GENERATING,
        active_plan_id="plan_001",
    )

    recovered = SimpleNamespace(
        trip_id="trip_001",
        user_id="user_001",
        status=TripStatus.GENERATED,
        active_plan_id="plan_001",
    )

    class Repository:
        def get_by_user_id(self, user_id):
            assert user_id == "user_001"
            return [stale]

        def recover_stale_generation(self, **kwargs):
            return recovered

    service = make_service(Repository())

    result = service.get_my_trips(user_id="user_001")

    assert result == [recovered]


def test_owned_trip_lookup_recovers_stale_generation():
    stale = SimpleNamespace(
        trip_id="trip_001",
        user_id="user_001",
        status=TripStatus.GENERATING,
        active_plan_id="plan_001",
    )

    recovered = SimpleNamespace(
        trip_id="trip_001",
        user_id="user_001",
        status=TripStatus.GENERATED,
        active_plan_id="plan_001",
    )

    class Repository:
        def get_by_id(self, trip_id):
            assert trip_id == "trip_001"
            return stale

        def recover_stale_generation(self, **kwargs):
            return recovered

    service = make_service(Repository())

    result = service._get_owned_trip_or_raise(
        user_id="user_001",
        trip_id="trip_001",
    )

    assert result is recovered
