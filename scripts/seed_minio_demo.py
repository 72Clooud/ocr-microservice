import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError

from config import settings

DEMO_FILES_DIR = Path("/demo-files")
OBJECT_PREFIX = "faktury/2026/"


def wait_for_bucket(client, bucket: str, retries: int = 15, delay: float = 2) -> None:
    for _ in range(retries):
        try:
            client.head_bucket(Bucket=bucket)
            return
        except ClientError:
            client.create_bucket(Bucket=bucket)
            return
        except EndpointConnectionError:
            time.sleep(delay)
    print("MinIO did not become reachable in time.", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    if not settings.MINIO_INTERNAL_ENDPOINT or not settings.MINIO_ROOT_USER:
        print("MinIO configuration is missing (MINIO_INTERNAL_ENDPOINT / MINIO_ROOT_USER).", file=sys.stderr)
        sys.exit(1)

    client = boto3.client(
        "s3",
        endpoint_url=settings.MINIO_INTERNAL_ENDPOINT,
        aws_access_key_id=settings.MINIO_ROOT_USER,
        aws_secret_access_key=settings.MINIO_ROOT_PASSWORD,
    )
    bucket = settings.BUCKET_NAME or "invoices"
    wait_for_bucket(client, bucket)

    files = sorted(p for p in DEMO_FILES_DIR.iterdir() if p.is_file())
    for src in files:
        client.upload_file(str(src), bucket, OBJECT_PREFIX + src.name)

    print(f"seeded {len(files)} file(s) into {bucket}/{OBJECT_PREFIX}")


if __name__ == "__main__":
    main()
