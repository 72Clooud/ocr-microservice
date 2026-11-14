from functools import lru_cache
from typing import Any

import boto3
import redis
from sqlalchemy import Engine, create_engine

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

@lru_cache
def get_db_engine() -> Engine:
    return create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
    )

@lru_cache
def get_s3_client() -> Any:
    if not settings.MINIO_INTERNAL_ENDPOINT or not settings.MINIO_ROOT_USER:
        raise ValueError("MinIO configuration is missing.")
    return boto3.client(
        "s3",
        endpoint_url=settings.MINIO_INTERNAL_ENDPOINT,
        aws_access_key_id=settings.MINIO_ROOT_USER,
        aws_secret_access_key=settings.MINIO_ROOT_PASSWORD,
    )
