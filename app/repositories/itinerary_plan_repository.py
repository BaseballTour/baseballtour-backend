from datetime import date, datetime

from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.client import Client
from google.cloud.firestore_v1.transaction import transactional

from app.core.firebase import get_firestore_client
from app.schemas.itinerary_plan import (
    ItineraryPlanDay,
    ItineraryPlanDocument,
    ItineraryPlanRecord,
)
from app.schemas.trip import TripStatus


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
        day_date = data.get("date")
        if isinstance(day_date, date) and not isinstance(
            day_date,
            datetime,
        ):
            data["date"] = day_date.isoformat()
        serialized.append(data)

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
    ) -> ItineraryPlanRecord:
        """
        새 일정 Plan 저장과 Trip 상태 갱신을 transaction으로 처리합니다.

        기존 ACTIVE Plan이 있으면 ARCHIVED로 변경하고,
        새 Plan을 ACTIVE로 저장한 뒤 Trip의 activePlanId와
        status를 갱신합니다.
        """

        plan_reference = self._collection.document()
        trip_reference = self._trip_collection.document(
            trip_id
        )

        previous_plan_reference = (
            self._collection.document(previous_plan_id)
            if previous_plan_id is not None
            else None
        )

        transaction = self._client.transaction()
        plan_data = plan.model_dump(
            by_alias=True,
            exclude_none=False,
        )
        plan_data["days"] = _serialize_days_for_firestore(
            plan.days
        )

        @transactional
        def commit(transaction) -> None:
            if previous_plan_reference is not None:
                transaction.update(
                    previous_plan_reference,
                    {
                        "status": "ARCHIVED",
                        "updatedAt": plan.updated_at,
                    },
                )

            transaction.set(
                plan_reference,
                plan_data,
            )

            transaction.update(
                trip_reference,
                {
                    "status": TripStatus.GENERATED.value,
                    "activePlanId": plan_reference.id,
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
