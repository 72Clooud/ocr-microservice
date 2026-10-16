from datetime import date
from pydantic import BaseModel, Field
from typing import Optional, Union, List
from enum import Enum

class InvoiceTaskRequest(BaseModel):
    task_id: str
    file_path: str
    webhook_url: str

class InvoiceTaskResponse(BaseModel):
    message: str
    task_id: str
    status: str

class Company(BaseModel):
    model_config = {"extra": "ignore"}
    name: Optional[str] = None
    address: Optional[str] = None
    vat_id: Optional[str] = None

class LineItem(BaseModel):
    model_config = {"extra": "ignore"}
    description: Optional[str] = None
    quantity: Optional[Union[float, str]] = None
    net_value: Optional[Union[float, str]] = None
    var_rate: Optional[Union[float, str]] = None

class Summary(BaseModel):
    model_config = {"extra": "ignore"}
    total_net: Optional[Union[float, str]] = None
    total_vat: Optional[Union[float, str]] = None
    total_due: Optional[Union[float, str]] = None
    currency: Optional[str] = None

class Dates(BaseModel):
    model_config = {"extra": "ignore"}
    issue_date: Optional[str] = None
    sale_date: Optional[str] = None
    due_date: Optional[str] = None

class InvoiceData(BaseModel):
    model_config = {"extra": "ignore"}
    invoice_number: Optional[str] = None
    iban: Optional[str] = None
    dates: Optional[Dates] = None
    seller: Optional[Company] = None
    buyer: Optional[Company] = None
    line_items: Optional[List[LineItem]] = None
    summary: Optional[Summary] = None

class WebhookSuccessPayload(BaseModel):
    task_id: str
    status: str = "SUCCESS"
    data: InvoiceData

class FileTypePrefixes(Enum):
    PDF_PREFIX = b"%PDF-"
    JPG_PREFIX = b"\xff\xd8\xff"
    PNG_PREFIX = b"\x89PNG\r\n\x1a\n"


class PodStatusResponse(BaseModel):
    configured: bool
    pod_id: Optional[str] = None
    status: Optional[str] = None
    health_ready: bool = False
    llm_url: Optional[str] = None
    gpu: Optional[str] = None
    cost_per_hr: Optional[float] = None
    started_at: Optional[str] = None
    uptime_seconds: Optional[int] = None


class PodActionResponse(BaseModel):
    message: str
    pod_id: Optional[str] = None
    llm_url: Optional[str] = None
    status: Optional[str] = None


class InvoiceReportRequest(BaseModel):
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    date_field: Optional[str] = Field("issue_date", pattern=r"^(issue_date|created_at)$")
    status_id: Optional[int] = None
    uploaded_by: Optional[int] = None
    supplier_id: Optional[int] = None
    currency: Optional[str] = Field(None, max_length=3)
    limit: Optional[int] = Field(50000, ge=1, le=100000)


class InvoiceReportResponse(BaseModel):
    file_path: str
    bucket: str
    filename: str
    download_url: Optional[str] = None
    rows_count: int
    generated_at: str



