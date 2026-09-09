from datetime import datetime, timezone
from hashlib import sha256
import secrets

from google.cloud.firestore_v1.client import Client
from google.cloud.firestore_v1.transaction import transactional

from app.core.firebase import get_firestore_client


class TripShareRepository:
    """여행별 공유 상태와 공개 토큰 인덱스를 관리합니다."""

    SHARES_COLLECTION = "tripShares"
    TOKENS_COLLECTION = "tripShareTokens"

    def __init__(self, client: Client | None = None) -> None:
        self._client = client or get_firestore_client()
        self._shares = self._client.collection(self.SHARES_COLLECTION)
        self._tokens = self._client.collection(self.TOKENS_COLLECTION)
        self._trips = self._client.collection("trips")

    @staticmethod
    def _token_hash(token: str) -> str:
        return sha256(token.encode("utf-8")).hexdigest()

    def issue(
        self,
        *,
        trip_id: str,
        user_id: str,
        expected_plan_id: str | None = None,
    ) -> str | None:
        """소유자에게 활성 토큰을 발급하거나 기존 토큰을 반환합니다.

        여행이 없거나 소유자가 다르면 None을 반환합니다.
        """
        share_ref = self._shares.document(trip_id)
        trip_ref = self._trips.document(trip_id)
        transaction = self._client.transaction()

        @transactional
        def commit(transaction) -> str | None:
            trip_snapshot = trip_ref.get(transaction=transaction)
            if not trip_snapshot.exists:
                return None

            trip_data = trip_snapshot.to_dict() or {}
            if trip_data.get("userId") != user_id:
                return None

            if expected_plan_id is not None:
                if (
                    trip_data.get("status")
                    not in {"GENERATED", "COMPLETED", "GENERATING"}
                    or trip_data.get("activePlanId") != expected_plan_id
                ):
                    return None

                plan_snapshot = (
                    self._client.collection("itineraryPlans")
                    .document(expected_plan_id)
                    .get(transaction=transaction)
                )
                if not plan_snapshot.exists:
                    return None
                plan_data = plan_snapshot.to_dict() or {}
                if (
                    plan_data.get("tripId") != trip_id
                    or plan_data.get("userId") != user_id
                    or plan_data.get("status") != "ACTIVE"
                ):
                    return None

            share_snapshot = share_ref.get(transaction=transaction)
            share_data = (
                share_snapshot.to_dict() or {}
                if share_snapshot.exists
                else {}
            )

            if share_data.get("isActive"):
                existing_token = share_data.get("token")
                if existing_token:
                    return existing_token

            token = secrets.token_urlsafe(32)
            token_hash = self._token_hash(token)
            now = datetime.now(timezone.utc)

            transaction.set(
                share_ref,
                {
                    "tripId": trip_id,
                    "userId": user_id,
                    "token": token,
                    "tokenHash": token_hash,
                    "isActive": True,
                    "createdAt": now,
                    "updatedAt": now,
                    "revokedAt": None,
                },
            )
            transaction.set(
                self._tokens.document(token_hash),
                {
                    "tripId": trip_id,
                    "isActive": True,
                    "createdAt": now,
                },
            )
            return token

        return commit(transaction)

    def revoke(self, *, trip_id: str, user_id: str) -> bool:
        """현재 활성 공유를 해제합니다. 이미 해제되었으면 False입니다."""
        share_ref = self._shares.document(trip_id)
        trip_ref = self._trips.document(trip_id)
        transaction = self._client.transaction()

        @transactional
        def commit(transaction) -> bool:
            trip_snapshot = trip_ref.get(transaction=transaction)
            if not trip_snapshot.exists:
                return False
            if (trip_snapshot.to_dict() or {}).get("userId") != user_id:
                return False

            share_snapshot = share_ref.get(transaction=transaction)
            if not share_snapshot.exists:
                return False

            share_data = share_snapshot.to_dict() or {}
            if not share_data.get("isActive"):
                return False

            token_hash = share_data.get("tokenHash")
            if not token_hash:
                return False

            now = datetime.now(timezone.utc)
            transaction.update(
                share_ref,
                {
                    "token": None,
                    "isActive": False,
                    "updatedAt": now,
                    "revokedAt": now,
                },
            )
            transaction.delete(self._tokens.document(token_hash))
            return True

        return commit(transaction)

    def get_active_trip_id(self, token: str) -> str | None:
        """활성 토큰에 연결된 여행 ID를 반환합니다."""
        token_hash = self._token_hash(token)
        token_snapshot = self._tokens.document(token_hash).get()
        if not token_snapshot.exists:
            return None

        token_data = token_snapshot.to_dict() or {}
        if not token_data.get("isActive"):
            return None

        trip_id = token_data.get("tripId")
        if not isinstance(trip_id, str) or not trip_id:
            return None

        share_snapshot = self._shares.document(trip_id).get()
        if not share_snapshot.exists:
            return None

        share_data = share_snapshot.to_dict() or {}
        if (
            not share_data.get("isActive")
            or share_data.get("tokenHash") != token_hash
        ):
            return None

        return trip_id

    def get_active_bundle(self, token: str):
        """활성 공유의 여행과 Plan을 일관된 스냅샷으로 조회합니다."""
        from app.schemas.itinerary_plan import (
            ItineraryPlanRecord,
            ItineraryPlanStatus,
        )
        from app.schemas.trip import TripRecord, TripStatus

        if not isinstance(token, str) or not token or len(token) > 128:
            return None

        token_hash = self._token_hash(token)
        token_ref = self._tokens.document(token_hash)
        transaction = self._client.transaction()

        @transactional
        def read(transaction):
            token_snapshot = token_ref.get(transaction=transaction)
            if not token_snapshot.exists:
                return None

            token_data = token_snapshot.to_dict() or {}
            if not token_data.get("isActive"):
                return None

            trip_id = token_data.get("tripId")
            if not isinstance(trip_id, str) or not trip_id:
                return None

            share_snapshot = (
                self._shares.document(trip_id)
                .get(transaction=transaction)
            )
            trip_snapshot = (
                self._trips.document(trip_id)
                .get(transaction=transaction)
            )
            if not share_snapshot.exists or not trip_snapshot.exists:
                return None

            share_data = share_snapshot.to_dict() or {}
            trip_data = trip_snapshot.to_dict() or {}
            if (
                not share_data.get("isActive")
                or share_data.get("tokenHash") != token_hash
                or share_data.get("userId") != trip_data.get("userId")
            ):
                return None

            if trip_data.get("status") not in {
                "GENERATED", "COMPLETED", "GENERATING"
            }:
                return None

            plan_id = trip_data.get("activePlanId")
            if not isinstance(plan_id, str) or not plan_id:
                return None

            plan_snapshot = (
                self._client.collection("itineraryPlans")
                .document(plan_id)
                .get(transaction=transaction)
            )
            if not plan_snapshot.exists:
                return None

            plan_data = plan_snapshot.to_dict() or {}
            if (
                plan_data.get("tripId") != trip_id
                or plan_data.get("userId") != trip_data.get("userId")
                or plan_data.get("status") != "ACTIVE"
            ):
                return None

            trip = TripRecord(trip_id=trip_id, **trip_data)
            plan = ItineraryPlanRecord(plan_id=plan_id, **plan_data)
            return trip, plan

        return read(transaction)

    def delete_trip(self, *, trip_id: str) -> bool:
        """여행과 공유 문서·토큰 인덱스를 원자적으로 삭제합니다."""
        from re import fullmatch

        trip_ref = self._trips.document(trip_id)
        share_ref = self._shares.document(trip_id)
        transaction = self._client.transaction()

        @transactional
        def commit(transaction) -> bool:
            trip_snapshot = trip_ref.get(transaction=transaction)
            share_snapshot = share_ref.get(transaction=transaction)

            if not trip_snapshot.exists:
                return False

            share_data = (
                share_snapshot.to_dict() or {}
                if share_snapshot.exists
                else {}
            )
            token_hash = share_data.get("tokenHash")

            if token_hash is not None:
                if (
                    not isinstance(token_hash, str)
                    or fullmatch(r"[0-9a-f]{64}", token_hash) is None
                ):
                    raise ValueError("Invalid trip share token hash")

            # 모든 읽기를 마친 뒤 쓰기를 수행합니다.
            if token_hash:
                transaction.delete(self._tokens.document(token_hash))

            transaction.delete(share_ref)
            transaction.delete(trip_ref)
            return True

        return commit(transaction)
