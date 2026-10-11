from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app
from dependencies import get_runpod_service


def test_process_invoice_success():
    client = TestClient(app)
    
    payload = {
        "task_id": "12345",
        "file_path": "invoices/2026/06/invoice_abc.pdf",
        "webhook_url": "https://example.com/webhooks/ocr"
    }
    
    with patch("routers.invoices.process_invoice_task.delay") as mock_delay:
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
    
    with patch("routers.invoices.process_invoice_task.delay") as mock_delay:
        response = client.post("/api/v1/process_invoice", json=payload)
        mock_delay.assert_not_called()
        
    assert response.status_code == 422


def test_get_pod_status_unconfigured():
    client = TestClient(app)
    mock_service = MagicMock()
    mock_service.get_status.return_value = {
        "configured": False,
        "pod_id": None,
        "status": None,
        "health_ready": False,
        "llm_url": None,
        "gpu": None,
        "cost_per_hr": None,
        "started_at": None,
        "uptime_seconds": None,
    }
    app.dependency_overrides[get_runpod_service] = lambda: mock_service

    try:
        response = client.get("/api/v1/pod/status")
        assert response.status_code == 200
        data = response.json()
        assert data == {
            "configured": False,
            "pod_id": None,
            "status": None,
            "health_ready": False,
            "llm_url": None,
            "gpu": None,
            "cost_per_hr": None,
            "started_at": None,
            "uptime_seconds": None,
        }
    finally:
        app.dependency_overrides.clear()


def test_get_pod_status_running():
    client = TestClient(app)
    mock_service = MagicMock()
    mock_service.get_status.return_value = {
        "configured": True,
        "pod_id": "test-pod-123",
        "status": "RUNNING",
        "health_ready": True,
        "llm_url": "https://test-pod-123-8080.proxy.runpod.net/v1",
        "gpu": "NVIDIA RTX A5000",
        "cost_per_hr": 0.27,
        "started_at": "2026-10-11T11:55:30.73Z",
        "uptime_seconds": 120,
    }
    app.dependency_overrides[get_runpod_service] = lambda: mock_service

    try:
        response = client.get("/api/v1/pod/status")
        assert response.status_code == 200
        data = response.json()
        assert data["configured"] is True
        assert data["pod_id"] == "test-pod-123"
        assert data["status"] == "RUNNING"
        assert data["health_ready"] is True
        assert data["gpu"] == "NVIDIA RTX A5000"
        assert data["cost_per_hr"] == 0.27
        assert data["uptime_seconds"] == 120
    finally:
        app.dependency_overrides.clear()


def test_start_pod_endpoint():
    client = TestClient(app)
    mock_service = MagicMock()
    mock_service.start_pod.return_value = {
        "message": "Pod is already running",
        "pod_id": "test-pod-123",
        "llm_url": "https://test-pod-123-8080.proxy.runpod.net/v1",
        "status": "RUNNING",
    }
    app.dependency_overrides[get_runpod_service] = lambda: mock_service

    try:
        response = client.post("/api/v1/pod/start")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Pod is already running"
        assert data["pod_id"] == "test-pod-123"
        assert data["status"] == "RUNNING"
    finally:
        app.dependency_overrides.clear()


def test_stop_pod_endpoint():
    client = TestClient(app)
    mock_service = MagicMock()
    mock_service.stop_pod.return_value = {
        "message": "Pod is already stopped",
        "pod_id": "test-pod-123",
        "status": "EXITED",
    }
    app.dependency_overrides[get_runpod_service] = lambda: mock_service

    try:
        response = client.post("/api/v1/pod/stop")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Pod is already stopped"
        assert data["pod_id"] == "test-pod-123"
        assert data["status"] == "EXITED"
    finally:
        app.dependency_overrides.clear()


