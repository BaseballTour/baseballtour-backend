from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any

from google.cloud.firestore_v1.client import Client

from app.core.firebase import get_firestore_client


class TourApiCacheRepository:
    """Cloud Run 인스턴스 사이에서 공유하는 TourAPI 원시 응답 캐시."""

    COLLECTION_NAME = "tourApiResponseCache"

    def __init__(self, client: Client | None = None) -> None:
        self._client = client

    @staticmethod
    def cache_key(endpoint: str, params: dict[str, Any]) -> str:
        canonical = json.dumps(
            {"endpoint": endpoint, "params": params},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return sha256(canonical.encode("utf-8")).hexdigest()

    @property
    def _collection(self):
        client = self._client or get_firestore_client()
        return client.collection(self.COLLECTION_NAME)

    def get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any] | None:
        snapshot = self._collection.document(
            self.cache_key(endpoint, params)
        ).get()
        if not snapshot.exists:
            return None
        data = snapshot.to_dict() or {}
        expires_at = data.get("expiresAt")
        if not isinstance(expires_at, datetime):
            return None
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            return None
        payload = data.get("payload")
        return payload if isinstance(payload, dict) else None

    def set(
        self,
        endpoint: str,
        params: dict[str, Any],
        payload: dict[str, Any],
        *,
        ttl_seconds: int,
    ) -> None:
        now = datetime.now(timezone.utc)
        self._collection.document(self.cache_key(endpoint, params)).set(
            {
                "endpoint": endpoint,
                "payload": payload,
                "createdAt": now,
                "expiresAt": now + timedelta(seconds=ttl_seconds),
            }
        )
