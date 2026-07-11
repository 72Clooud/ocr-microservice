import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://azurite:10000/devstoreaccount1;")
os.environ.setdefault("AZURE_STORAGE_CONTAINER_NAME", "invoices")
os.environ.setdefault("OLLAMA_HOST", "http://ollama:11434")
os.environ.setdefault("REDIS_PASSWORD", "test-redis-password")
os.environ.setdefault("WEBHOOK_SECRET_TOKEN", "test-webhook-secret")

