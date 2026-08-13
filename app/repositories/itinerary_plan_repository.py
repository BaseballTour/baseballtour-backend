from datetime import datetime

from google.cloud.firestore_v1.client import Client
from google.cloud.firestore_v1.transaction import transactional

from app.core.firebase import get_firestore_client
from app.schemas.itinerary_plan import (
    ItineraryPlanDay,
    ItineraryPlanDocument,
    ItineraryPlanRecord,
)
from app.schemas.trip import TripStatus


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
                plan.model_dump(
                    by_alias=True,
                    exclude_none=False,
                ),
            )

            transaction.update(
                trip_reference,
                {
                    "status": TripStatus.GENERATED.value,
                    "activePlanId": plan_reference.id,
                    "updatedAt": plan.updated_at,
                },
            )

        commit(transaction)

        return ItineraryPlanRecord(
            plan_id=plan_reference.id,
            **plan.model_dump(),
        )


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
                "days": [
                    day.model_dump(
                        by_alias=True,
                        exclude_none=False,
                    )
                    for day in days
                ],
                "totalTravelMinutes": total_travel_minutes,
                "updatedAt": updated_at,
            }
        )

        return self.get_by_id(
            plan_id
        )
