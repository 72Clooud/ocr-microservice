import logging
import requests
import io
import base64
import boto3
import re
from PIL import Image
from celery import Celery
from ollama import Client as OllamaClient

from config import settings
from prompts import INVOICE_EXTRACTION_PROMPT
from schemas import (
    InvoiceData, WebhookSuccessPayload
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

s3_client = boto3.client(
    "s3",
    endpoint_url=settings.MINIO_INTERNAL_ENDPOINT,
    aws_access_key_id=settings.MINIO_ROOT_USER,
    aws_secret_access_key=settings.MINIO_ROOT_PASSWORD,
)
ollama_client = OllamaClient(host=settings.OLLAMA_HOST)

celery_app = Celery('ocr_worker', broker=settings.CELERY_BROKER_URL)
celery_app.conf.update(
    worker_concurrency=1,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_time_limit=300
)

def _clean_extracted_data(extracted_data_str: str) -> str:
    if not extracted_data_str:
        return "{}"
    match_code_block = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", extracted_data_str, re.IGNORECASE)
    if match_code_block:
        return match_code_block.group(1).strip()
    
    match_json = re.search(r"\{[\s\S]*\}", extracted_data_str)
    if match_json:
        return match_json.group(0).strip()

    return extracted_data_str.strip()

def _send_webhook(url: str, payload_dict: dict, task_id: str) -> None:
    try:
        resp = requests.post(url, json=payload_dict, timeout=10)
        resp.raise_for_status()
        logger.info(f"[{task_id}] Successfully completed. Webhook sent")
    except Exception as exc:
        logger.error(f"[{task_id}] Error sending webhook: {exc}")
        raise

@celery_app.task(name="process_invoice", bind=True, max_retries=3)
def process_invoice_task(self, task_id: int, file_path: str, webhook_url: str) -> bool:
    try:
        file_obj = s3_client.get_object(Bucket=settings.BUCKET_NAME, Key=file_path)
        file_bytes = file_obj['Body'].read()
    except Exception as exc:
        logger.error(f"[{task_id}] MinIO download error: {exc}")
        raise self.retry(exc=exc, countdown=60)
    
    img = Image.open(io.BytesIO(file_bytes))
    if img.mode != "RGB":
        img = img.convert("RGB")
    max_size = 1600
    if img.width > max_size or img.height > max_size:
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    temp_buffer = io.BytesIO()
    img.save(temp_buffer, format="JPEG")
    base64_image = base64.b64encode(temp_buffer.getvalue()).decode('utf-8')
    
    try:
        response = ollama_client.chat(
            model="glm-ocr:q8_0",
            format="json",
            options={"num_ctx": 4096, "temperature": 0.0},
            messages=[{
                "role": "user",
                "content": INVOICE_EXTRACTION_PROMPT,
                "images": [base64_image]
            }],
        )
        extracted_data_str = response["message"]["content"]
    except Exception as exc:
        logger.error(f"[{task_id}] Ollama model error: {exc}")
        raise self.retry(exc=exc, countdown=60)
    
    cleaned_str = _clean_extracted_data(extracted_data_str)

    try:
        parsed_data = InvoiceData.model_validate_json(cleaned_str)
    except Exception as exc:
        logger.error(f"[{task_id}] Pydantic validation error: {exc}. Raw response: {extracted_data_str!r}")
        raise self.retry(exc=exc, countdown=60)
    
    payload_model = WebhookSuccessPayload(task_id=task_id, data=parsed_data)

    _send_webhook(
        webhook_url,
        payload_model.model_dump(),
        task_id
        )    

    return True