import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("MINIO_ROOT_USER", "test-user")
os.environ.setdefault("MINIO_ROOT_PASSWORD", "test-password")
os.environ.setdefault("MINIO_INTERNAL_ENDPOINT", "http://minio:9000")
os.environ.setdefault("MINIO_EXTERNAL_URL", "http://localhost:9000")
os.environ.setdefault("BUCKET_NAME", "test-bucket")
os.environ.setdefault("OLLAMA_HOST", "http://ollama:11434")
os.environ.setdefault("REDIS_PASSWORD", "test-redis-password")
os.environ.setdefault("WEBHOOK_SECRET_TOKEN", "test-webhook-secret")

