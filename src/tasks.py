import logging
import requests
import io
import base64
import boto3
import re
import pypdfium2 as pdfium 

from PIL import Image
from celery import Celery
from ollama import Client as OllamaClient

from config import settings
from prompts import INVOICE_EXTRACTION_PROMPT
from schemas import (
    InvoiceData, WebhookSuccessPayload, FileTypePrefixes
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

def _preprocess_image(image_bytes: bytes, max_size: int = 1344) -> bytes:
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != "RGB":
        img = img.convert("RGB")
    if img.width > max_size or img.height > max_size:
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    image_buffer = io.BytesIO()
    img.save(image_buffer, format="JPEG")
    img_bytes = image_buffer.getvalue()

    return img_bytes

def _pdf_to_image(pdf_bytes: bytes, dpi: int = 300) -> bytes:
    scale_factor = dpi / 72.0

    pdf = pdfium.PdfDocument(pdf_bytes)
    page = pdf.get_page(0)
    bitmap = page.render(scale=scale_factor)
    pil_image = bitmap.to_pil()
    image_buffer = io.BytesIO()
    pil_image.save(image_buffer, format="PNG")
    img_bytes = image_buffer.getvalue()
    processed_image = _preprocess_image(img_bytes)

    return processed_image

@celery_app.task(name="process_invoice", bind=True, max_retries=3)
def process_invoice_task(self, task_id: int, file_path: str, webhook_url: str) -> bool:
    try:
        file_obj = s3_client.get_object(Bucket=settings.BUCKET_NAME, Key=file_path)
        file_bytes = file_obj['Body'].read()
    except Exception as exc:
        logger.error(f"[{task_id}] MinIO download error: {exc}")
        raise self.retry(exc=exc, countdown=60)

    if file_bytes.startswith(FileTypePrefixes.PDF_PREFIX.value):
        img = _pdf_to_image(file_bytes)
    elif file_bytes.startswith(FileTypePrefixes.PNG_PREFIX.value) or file_bytes.startswith(FileTypePrefixes.JPG_PREFIX.value):
        img = _preprocess_image(file_bytes)
    else:
        raise ValueError("Incorrect file format")

    try:
        response = ollama_client.chat(
            model="glm-ocr:q8_0",
            format="json",
            options={"num_ctx": 8192, "temperature": 0.0},
            messages=[{
                "role": "user",
                "content": INVOICE_EXTRACTION_PROMPT,
                "images": [img]
            }],
        )
        extracted_data_str = response["message"]["content"]
        logger.info(
            f"[{task_id}] Ollama response: prompt_eval_count={response.get('prompt_eval_count')}, "
            f"eval_count={response.get('eval_count')}, "
            f"total_duration={response.get('total_duration')}"
        )
        logger.info(f"[{task_id}] Raw model output: {extracted_data_str!r}")
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