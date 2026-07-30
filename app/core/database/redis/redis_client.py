import redis
from typing import Optional

from app.core.conf.config import settings


_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """
    Returns a singleton Redis client.
    Uses the REDIS_URL from settings.
    """
    global _redis_client

    if _redis_client is None:
        _redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=True,
            health_check_interval=30
        )

    return _redis_client


def get_redis_dependency() -> redis.Redis:
    """Use this with FastAPI's Depends()"""
    return get_redis_client()