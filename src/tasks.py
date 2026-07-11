import logging
import requests
import io
import base64
from azure.storage.blob import BlobServiceClient
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

blob_service = BlobServiceClient.from_connection_string(
    settings.AZURE_STORAGE_CONNECTION_STRING
)
container_client = blob_service.get_container_client(
    settings.AZURE_STORAGE_CONTAINER_NAME
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
    return extracted_data_str.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

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
        blob_client = container_client.get_blob_client(file_path)
        file_bytes = blob_client.download_blob().readall()
    except Exception as exc:
        logger.error(f"[{task_id}] Azure Blob download error: {exc}")
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
            options={"num_ctx": 4096},
            messages=[{
                "role": "user",
                "content": INVOICE_EXTRACTION_PROMPT,
                "images": [base64_image]
            }],
        )
        extracted_data_str = response["message"]["content"]
    except Exception as exc:
        logger.error(f"[{task_id}] Ollam model error: {exc}")
        raise self.retry(exc=exc, countdown=60)
    
    cleaned_str = _clean_extracted_data(extracted_data_str)

    parsed_data = InvoiceData.model_validate_json(cleaned_str)
    
    payload_model = WebhookSuccessPayload(task_id=task_id, data=parsed_data)

    _send_webhook(
        webhook_url,
        payload_model.model_dump(),
        task_id
        )    

    return True