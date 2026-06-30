from pydantic import BaseModel, Field
from typing import Optional, Union, List

class InvoiceTaskRequest(BaseModel):
    task_id: str
    file_path: str
    webhook_url: str

class InvoiceTaskResponse(BaseModel):
    message: str
    task_id: str
    status: str

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

class WebhookSuccessPayload(BaseModel):
    task_id: str
    status: str = "SUCCESS"
    data: InvoiceData
