import json
from typing import Optional, Any, Callable
from app.core.database.redis.redis_client import get_redis_dependency
from fastapi import Depends
from redis import Redis

__all__ = [
    "RedisRepository",
    "get_redis_dependency",
]


class RedisRepository:
    """Generic key-value repository backed by Redis."""

    def __init__(
        self, client: Redis, prefix: str = "", default_ttl: Optional[int] = 300
    ):
        self.client = client
        self.prefix = prefix
        self.default_ttl = default_ttl

    def _key(self, key: str) -> str:
        return f"{self.prefix}:{key}" if self.prefix else key

    def get(self, key: str) -> Optional[Any]:
        return self.client.get(self._key(key))

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        payload = json.dumps(value) if not isinstance(value, (str, bytes)) else value
        ttl = ttl if ttl is not None else self.default_ttl
        return bool(self.client.set(self._key(key), payload, ex=ttl))

    def delete(self, key: str) -> bool:
        return bool(self.client.delete(self._key(key)))

    def exists(self, key: str) -> bool:
        return bool(self.client.exists(self._key(key)))

    def expire(self, key: str, ttl: int) -> bool:
        return bool(self.client.expire(self._key(key), ttl))

    def ttl(self, key: str) -> int:
        return self.client.ttl(self._key(key))

    def incr(self, key: str, amount: int = 1) -> int:
        return self.client.incrby(self._key(key), amount)


def get_redis_repository(
    prefix: str = "",
    default_ttl: Optional[int] = None,
) -> Callable[[Redis], RedisRepository]:
    """Factory that creates a dependency with the desired prefix/ttl."""

    def dependency(
        redis_client: Redis = Depends(get_redis_dependency),
    ) -> RedisRepository:
        return RedisRepository(
            client=redis_client,
            prefix=prefix,
            default_ttl=default_ttl,
        )

    return dependency
