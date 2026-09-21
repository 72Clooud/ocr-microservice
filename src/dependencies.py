from functools import lru_cache

import redis

from config import settings
from runpod import RunPodService


@lru_cache
def get_redis_client() -> redis.Redis:
    scheme = "rediss" if settings.REDIS_SSL else "redis"
    return redis.from_url(
        f"{scheme}://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/0",
        decode_responses=True,
    )


@lru_cache
def get_runpod_service() -> RunPodService:
    return RunPodService(redis_client=get_redis_client())