from unittest.mock import patch
from fastapi.testclient import TestClient

from main import app


def test_process_invoice_success():
    client = TestClient(app)
    
    payload = {
        "task_id": "12345",
        "file_path": "invoices/2026/06/invoice_abc.pdf",
        "webhook_url": "https://example.com/webhooks/ocr"
    }
    
    with patch("main.process_invoice_task.delay") as mock_delay:
        response = client.post("/api/v1/process_invoice", json=payload)
        
        # Verify Celery delay was called with the correct parameters
        mock_delay.assert_called_once_with(
            task_id="12345",
            file_path="invoices/2026/06/invoice_abc.pdf",
            webhook_url="https://example.com/webhooks/ocr"
        )
        
    assert response.status_code == 202
    data = response.json()
    assert data["message"] == "Task submitted to redis"
    assert data["task_id"] == "12345"
    assert data["status"] == "processing"


def test_process_invoice_missing_fields():
    client = TestClient(app)
    
    # Missing webhook_url
    payload = {
        "task_id": "12345",
        "file_path": "invoices/2026/06/invoice_abc.pdf"
    }
    
    with patch("main.process_invoice_task.delay") as mock_delay:
        response = client.post("/api/v1/process_invoice", json=payload)
        mock_delay.assert_not_called()
        
    assert response.status_code == 422
