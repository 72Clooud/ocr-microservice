import logging

from fastapi import FastAPI

from config import settings
from schemas import InvoiceTaskRequest, InvoiceTaskResponse
from tasks import process_invoice_task

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.PROJECT_NAME)

@app.post('/api/v1/process_invoice', response_model=InvoiceTaskResponse, status_code=202)
async def process_invoice(request: InvoiceTaskRequest) -> InvoiceTaskResponse:
    process_invoice_task.delay(
        task_id=request.task_id,
        file_path=request.file_path,
        webhook_url=request.webhook_url
    )

    return InvoiceTaskResponse(
        message="Task submitted to redis",
        task_id=request.task_id,
        status="processing"
    )