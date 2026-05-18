import uuid
import requests
import boto3
import logging
import io
import base64

from ollama import Client as OllamaClient
from fastapi import FastAPI, UploadFile, Form, BackgroundTasks
from PIL import Image

from config import settings
from prompts import INVOICE_EXTRACTION_PROMPT
from schemas import InvoiceData, WebhookSuccessResponse, WebhookErrorResponse


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.PROJECT_NAME)

s3_client = boto3.client(
    "s3",
    endpoint_url=settings.MINIO_INTERNAL_ENDPOINT,
    aws_access_key_id=settings.MINIO_ROOT_USER,
    aws_secret_access_key=settings.MINIO_ROOT_PASSWORD,
)

ollama_client = OllamaClient(host=settings.OLLAMA_HOST)

try:
    s3_client.create_bucket(Bucket=settings.BUCKET_NAME)
except Exception as e:
    logger.warning(f"Bucket check: {e}")


def process_invoice_background(
    task_id: str, file_name: str, file_bytes: bytes, webhook_url: str
):
    logger.info(f"[{task_id}] Started processing: {file_name}")
    try:
        file_key = f"{task_id}_{file_name}"
        s3_client.put_object(Bucket=settings.BUCKET_NAME, Key=file_key, Body=file_bytes)

        minio_url = f"{settings.MINIO_EXTERNAL_URL}/{settings.BUCKET_NAME}/{file_key}"
        logger.info(f"[{task_id}] Saved to MinIO: {minio_url}")

        img = Image.open(io.BytesIO(file_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")

        max_size = 1600
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

        temp_buffer = io.BytesIO()
        img.save(temp_buffer, format="JPEG")

        base64_image = base64.b64encode(temp_buffer.getvalue()).decode('utf-8')

        logger.info(f"[{task_id}] Calling Ollama model...")

        response = ollama_client.chat(
            model="glm-ocr:q8_0",
            options={
                "num_ctx": 4096
            },
            messages=[
                {
                    "role": "user",
                    "content": INVOICE_EXTRACTION_PROMPT,
                    "images": [base64_image],
                }
            ],
        )

        extracted_data_str = response["message"]["content"]
        cleaned_str = (
            extracted_data_str.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        parsed_data = InvoiceData.model_validate_json(cleaned_str)
        logger.info(f"[{task_id}] OCR analysis and validation successful")

        success_payload = WebhookSuccessResponse(
            task_id=task_id, minio_url=minio_url, data=parsed_data
        )

        resp = requests.post(webhook_url, json=success_payload.model_dump(), timeout=10)
        resp.raise_for_status()
        logger.info(f"[{task_id}] Webhook sent successfully.")

    except Exception as e:
        logger.error(f"[{task_id}] CRITICAL ERROR: {e}", exc_info=True)

        error_payload = WebhookErrorResponse(task_id=task_id, error=str(e))
        try:
            requests.post(webhook_url, json=error_payload.model_dump(), timeout=10)
        except Exception as webhook_error:
            logger.error(f"[{task_id}] Failed to send error webhook: {webhook_error}")


@app.post("/api/v1/process-invoice", status_code=202)
async def process_invoice(
    background_tasks: BackgroundTasks, file: UploadFile, webhook_url: str = Form(...)
):
    task_id = str(uuid.uuid4())

    file_bytes = await file.read()

    background_tasks.add_task(
        process_invoice_background,
        task_id=task_id,
        file_name=file.filename,
        file_bytes=file_bytes,
        webhook_url=webhook_url,
    )
    
    return {
        "message": "Invoice accepted for processing",
        "task_id": task_id,
        "status": "processing"
    }