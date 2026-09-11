from datetime import date, datetime

from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.client import Client
from google.cloud.firestore_v1.transaction import transactional

from app.core.firebase import get_firestore_client
from app.core.ids import new_prefixed_id
from app.schemas.itinerary_plan import (
    ItineraryPlanDay,
    ItineraryPlanDocument,
    ItineraryPlanRecord,
)
from app.models.itinerary import ItineraryQualitySummary
from app.schemas.trip import TripStatus


def _serialize_value_for_firestore(value):
    """중첩 구조의 순수 date만 ISO 문자열로 바꾸고 datetime은 보존합니다."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {
            key: _serialize_value_for_firestore(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_serialize_value_for_firestore(item) for item in value]
    return value


def _serialize_days_for_firestore(
    days: list[ItineraryPlanDay],
) -> list[dict]:
    """Firestore가 지원하지 않는 순수 date를 ISO 문자열로 변환합니다."""

    serialized: list[dict] = []

    for day in days:
        data = day.model_dump(
            by_alias=True,
            exclude_none=False,
        )
        serialized.append(_serialize_value_for_firestore(data))

    return serialized


class ItineraryPlanRepository:
    """Firestore itineraryPlans Collection 접근을 담당합니다."""

    COLLECTION_NAME = "itineraryPlans"

    def __init__(
        self,
        client: Client | None = None,
    ) -> None:
        self._client = client or get_firestore_client()
        self._collection = self._client.collection(
            self.COLLECTION_NAME
        )
        self._trip_collection = self._client.collection(
            "trips"
        )

    def get_by_id(
        self,
        plan_id: str,
    ) -> ItineraryPlanRecord | None:
        """일정 Plan ID로 문서를 조회합니다."""

        snapshot = self._collection.document(
            plan_id
        ).get()

        if not snapshot.exists:
            return None

        data = snapshot.to_dict() or {}

        return ItineraryPlanRecord(
            plan_id=snapshot.id,
            **data,
        )

    def commit_generated_plan(
        self,
        *,
        trip_id: str,
        plan: ItineraryPlanDocument,
        previous_plan_id: str | None,
        rejected_recommendation_place_ids: list[str],
        generation_lease_id: str | None = None,
    ) -> ItineraryPlanRecord:
        """소유권을 확인한 뒤 새 Plan과 Trip 상태를 원자적으로 저장합니다."""
        from app.core.exceptions import AppException

        plan_reference = self._collection.document(new_prefixed_id("plan"))
        trip_reference = self._trip_collection.document(trip_id)
        previous_plan_reference = (
            self._collection.document(previous_plan_id)
            if previous_plan_id is not None
            else None
        )
        transaction = self._client.transaction()

        plan_data = _serialize_value_for_firestore(
            plan.model_dump(
                by_alias=True,
                exclude_none=False,
            )
        )

        @transactional
        def commit(transaction) -> None:
            # Firestore transaction은 모든 읽기를 쓰기보다 먼저 수행합니다.
            trip_snapshot = trip_reference.get(transaction=transaction)
            if not trip_snapshot.exists:
                raise AppException(
                    status_code=404,
                    code="TRIP_NOT_FOUND",
                    message="여행을 찾을 수 없습니다.",
                )

            _require_generation_lease(
                trip_snapshot.to_dict() or {},
                generation_lease_id=generation_lease_id,
                expected_active_plan_id=previous_plan_id,
            )

            if previous_plan_reference is not None:
                previous_snapshot = previous_plan_reference.get(
                    transaction=transaction,
                )
                previous_data = (
                    previous_snapshot.to_dict() or {}
                    if previous_snapshot.exists
                    else {}
                )
                if (
                    not previous_snapshot.exists
                    or previous_data.get("tripId") != trip_id
                    or previous_data.get("status") != "ACTIVE"
                ):
                    raise AppException(
                        status_code=409,
                        code="TRIP_GENERATION_IN_PROGRESS",
                        message="기존 활성 일정이 변경되었습니다.",
                    )

            if previous_plan_reference is not None:
                transaction.update(
                    previous_plan_reference,
                    {
                        "status": "ARCHIVED",
                        "updatedAt": plan.updated_at,
                    },
                )

            transaction.set(plan_reference, plan_data)
            transaction.update(
                trip_reference,
                {
                    "status": TripStatus.GENERATED.value,
                    "activePlanId": plan_reference.id,
                    "generationLeaseId": None,
                    "rejectedRecommendationPlaceIds": (
                        rejected_recommendation_place_ids
                    ),
                    "updatedAt": plan.updated_at,
                },
            )

        commit(transaction)
        return ItineraryPlanRecord(
            plan_id=plan_reference.id,
            **plan.model_dump(),
        )


    def delete_all_by_trip_id(
        self,
        *,
        trip_id: str,
    ) -> int:
        """Trip에 속한 모든 일정 Plan을 삭제합니다."""

        query = self._collection.where(
            filter=FieldFilter(
                "tripId",
                "==",
                trip_id,
            )
        )

        snapshots = list(query.stream())

        for snapshot in snapshots:
            self._collection.document(
                snapshot.id
            ).delete()

        return len(snapshots)

    def delete_active_plan(
        self,
        *,
        trip_id: str,
        plan_id: str,
        updated_at: datetime,
    ) -> None:
        """
        현재 ACTIVE Plan을 삭제하고 Trip을 PLANNING 상태로 되돌립니다.

        Plan 삭제와 Trip의 activePlanId/status 갱신은
        하나의 transaction으로 처리합니다.
        """

        plan_reference = self._collection.document(
            plan_id
        )
        trip_reference = self._trip_collection.document(
            trip_id
        )

        transaction = self._client.transaction()

        @transactional
        def commit(transaction) -> None:
            transaction.delete(
                plan_reference
            )

            transaction.update(
                trip_reference,
                {
                    "status": TripStatus.PLANNING.value,
                    "activePlanId": None,
                    "updatedAt": updated_at,
                },
            )

        commit(transaction)



    def update_schedule(
        self,
        *,
        plan_id: str,
        days: list[ItineraryPlanDay],
        total_travel_minutes: int,
        updated_at: datetime,
    ) -> ItineraryPlanRecord | None:
        """편집된 일정과 총 이동시간을 저장합니다."""

        reference = self._collection.document(
            plan_id
        )

        reference.update(
            {
                "days": _serialize_days_for_firestore(days),
                "totalTravelMinutes": total_travel_minutes,
                "updatedAt": updated_at,
            }
        )

        return self.get_by_id(
            plan_id
        )

    def commit_regenerated_day(
        self,
        *,
        trip_id: str,
        plan_id: str,
        days: list[ItineraryPlanDay],
        updated_at: datetime,
        quality_summary: ItineraryQualitySummary | None = None,
        generation_lease_id: str | None = None,
    ) -> ItineraryPlanRecord:
        """현재 생성 요청만 활성 Plan의 하루를 교체할 수 있습니다."""
        from app.core.exceptions import AppException

        plan_reference = self._collection.document(plan_id)
        trip_reference = self._trip_collection.document(trip_id)

        total_travel_minutes = sum(
            item.travel_minutes_from_previous
            for day in days
            for item in day.items
        )
        total_distance = sum(
            item.travel_distance_meters_from_previous
            for day in days
            for item in day.items
        )
        transaction = self._client.transaction()

        @transactional
        def commit(transaction) -> None:
            trip_snapshot = trip_reference.get(transaction=transaction)
            if not trip_snapshot.exists:
                raise AppException(
                    status_code=404,
                    code="TRIP_NOT_FOUND",
                    message="여행을 찾을 수 없습니다.",
                )

            _require_generation_lease(
                trip_snapshot.to_dict() or {},
                generation_lease_id=generation_lease_id,
                expected_active_plan_id=plan_id,
            )

            plan_snapshot = plan_reference.get(transaction=transaction)
            plan_data = (
                plan_snapshot.to_dict() or {}
                if plan_snapshot.exists
                else {}
            )
            if (
                not plan_snapshot.exists
                or plan_data.get("tripId") != trip_id
                or plan_data.get("status") != "ACTIVE"
            ):
                raise AppException(
                    status_code=409,
                    code="TRIP_GENERATION_IN_PROGRESS",
                    message="기존 활성 일정이 변경되었습니다.",
                )

            update_data = {
                "days": _serialize_days_for_firestore(days),
                "totalTravelMinutes": total_travel_minutes,
                "totalTravelDistanceMeters": total_distance,
                "updatedAt": updated_at,
            }
            if quality_summary is not None:
                update_data["qualitySummary"] = quality_summary.model_dump(
                    by_alias=True,
                    mode="json",
                )
            transaction.update(
                plan_reference,
                update_data,
            )
            transaction.update(
                trip_reference,
                {
                    "status": TripStatus.GENERATED.value,
                    "generationLeaseId": None,
                    "updatedAt": updated_at,
                },
            )

        commit(transaction)

        updated = self.get_by_id(plan_id)
        if updated is None:
            raise RuntimeError("재생성한 일정 Plan을 조회할 수 없습니다.")
        return updated


def _require_generation_lease(
    data: dict,
    *,
    generation_lease_id: str | None,
    expected_active_plan_id: str | None,
) -> None:
    """현재 Trip 상태·lease·활성 Plan이 모두 일치해야 합니다."""
    from app.core.exceptions import AppException

    if (
        not generation_lease_id
        or data.get("status") != TripStatus.GENERATING.value
        or data.get("generationLeaseId") != generation_lease_id
        or data.get("activePlanId") != expected_active_plan_id
    ):
        raise AppException(
            status_code=409,
            code="TRIP_GENERATION_IN_PROGRESS",
            message="일정 생성 권한이 변경되었습니다. 여행 상태를 다시 조회해 주세요.",
        )
