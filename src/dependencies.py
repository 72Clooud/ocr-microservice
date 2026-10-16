from functools import lru_cache

import boto3
import redis
from sqlalchemy import Engine

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


@lru_cache
def get_db_engine() -> Engine:
    return settings.db_engine


@lru_cache
def get_s3_client():
    if not (settings.MINIO_INTERNAL_ENDPOINT and settings.MINIO_ROOT_USER):
        raise RuntimeError("MinIO is not configured in settings.")
    return boto3.client(
        "s3",
        endpoint_url=settings.MINIO_INTERNAL_ENDPOINT,
        aws_access_key_id=settings.MINIO_ROOT_USER,
        aws_secret_access_key=settings.MINIO_ROOT_PASSWORD,
    )