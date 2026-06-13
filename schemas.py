from pydantic import BaseModel, Field
from typing import Optional

class InvoiceTaskRequest(BaseModel):
    task_id: str
    file_path: str
    webhook_url: str

class InvoiceTaskResponse(BaseModel):
    message: str
    task_id: str
    status: str

class InvoiceData(BaseModel):
    nip: Optional[str] = None
    total_amount: Optional[float] = None

class WebhookSuccessPayload(BaseModel):
    task_id: str
    status: str = "SUCCESS"
    data: InvoiceData

class WebhookErrorPayload(BaseModel):
    task_id: str
    status: str = "FAILED"
    error: str

class WebhookHeaders(BaseModel):
    authorization: str = Field(alias="Authorization")
    content_type: str = Field(default="application/json", alias="Content-Type")