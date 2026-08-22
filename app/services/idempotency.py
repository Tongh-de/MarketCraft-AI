import json
from functools import lru_cache
from typing import Protocol
from uuid import UUID

from app.core.config import get_settings
from app.domain.models import PublishBatchResult


class IdempotencyStore(Protocol):
    def get(self, key: str) -> tuple[UUID, int, PublishBatchResult] | None: ...

    def put(
        self, key: str, campaign_id: UUID, version: int, result: PublishBatchResult
    ) -> None: ...


class InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._items: dict[str, tuple[UUID, int, PublishBatchResult]] = {}

    def get(self, key: str) -> tuple[UUID, int, PublishBatchResult] | None:
        return self._items.get(key)

    def put(
        self, key: str, campaign_id: UUID, version: int, result: PublishBatchResult
    ) -> None:
        self._items[key] = (campaign_id, version, result)


class RedisIdempotencyStore:
    def __init__(self, redis_url: str, ttl_seconds: int) -> None:
        from redis import Redis

        self.client = Redis.from_url(redis_url, decode_responses=True)
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _redis_key(key: str) -> str:
        return f"marketcraft:idempotency:{key}"

    def get(self, key: str) -> tuple[UUID, int, PublishBatchResult] | None:
        raw = self.client.get(self._redis_key(key))
        if not raw:
            return None
        payload = json.loads(raw)
        return (
            UUID(payload["campaign_id"]),
            payload["version"],
            PublishBatchResult.model_validate(payload["result"]),
        )

    def put(
        self, key: str, campaign_id: UUID, version: int, result: PublishBatchResult
    ) -> None:
        payload = {
            "campaign_id": str(campaign_id),
            "version": version,
            "result": result.model_dump(mode="json"),
        }
        self.client.setex(
            self._redis_key(key), self.ttl_seconds, json.dumps(payload, ensure_ascii=False)
        )


@lru_cache
def get_idempotency_store() -> IdempotencyStore:
    settings = get_settings()
    if settings.idempotency_mode == "redis":
        return RedisIdempotencyStore(
            settings.redis_url, settings.idempotency_ttl_seconds
        )
    return InMemoryIdempotencyStore()
