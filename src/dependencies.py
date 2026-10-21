from functools import lru_cache

import redis

from config import settings
from runpod import RunPodService


@lru_cache
def get_redis_client() -> redis.Redis:
    return redis.from_url(
        settings.APP_REDISS_URL,
        decode_responses=True,
    )

@lru_cache
def get_runpod_service() -> RunPodService:
    return RunPodService(redis_client=get_redis_client())