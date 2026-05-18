from enum import Enum
from typing import List, Optional, Union 
from pydantic import BaseModel

class Company(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    vat_id: Optional[str] = None

class LineItem(BaseModel):
    description: Optional[str] = None
    quantity: Optional[Union[float, str]] = None
    net_value: Optional[Union[float, str]] = None
    var_rate: Optional[Union[float, str]] = None

class Summary(BaseModel):
    total_net: Optional[Union[float, str]] = None
    total_vat: Optional[Union[float, str]] = None
    total_due: Optional[Union[float, str]] = None
    currency: Optional[str] = None

class InvoiceData(BaseModel):
    invoice_number: Optional[str] = None
    seller: Optional[Company] = None
    buyer: Optional[Company] = None
    line_items: Optional[List[LineItem]] = None
    summary: Optional[Summary] = None

class TaskStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = 'FAILED'
    PROCESSING = 'PROCESSING'

class WebhookResponseBase(BaseModel):
    status: TaskStatus
    task_id: str

class WebhookSuccessResponse(WebhookResponseBase):
    status: TaskStatus = TaskStatus.SUCCESS
    minio_url: str
    data: InvoiceData

class WebhookErrorResponse(WebhookResponseBase):
    status: TaskStatus = TaskStatus.FAILED
    error: str