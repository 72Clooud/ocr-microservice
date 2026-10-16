from datetime import date
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from main import app
from dependencies import get_db_engine, get_s3_client
from reports import generate_invoices_report


def test_generate_invoices_report_service_default_bucket():
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    fake_df = pd.DataFrame([
        {
            "invoice_id": 1,
            "invoice_number": "FV/2026/01",
            "issue_date": "2026-01-15",
            "created_at": "2026-01-15 10:00:00",
            "currency": "PLN",
            "net_amount": 1000.0,
            "gross_amount": 1230.0,
            "status_id": 2,
            "supplier_id": 5,
            "uploaded_by": 10,
            "rejection_reason": None,
            "file_path": "invoices/2026/01/fv.pdf",
        }
    ])

    mock_s3 = MagicMock()

    with patch("pandas.read_sql", return_value=fake_df) as mock_read_sql:
        result = generate_invoices_report(
            engine=mock_engine,
            s3_client=mock_s3,
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
            status_id=2,
            uploaded_by=10,
            currency="PLN",
            limit=500,
        )

    assert result["bucket"] == "reports"
    assert result["rows_count"] == 1
    assert result["file_path"].startswith("invoices/raport_faktury_")
    assert result["filename"].endswith(".xlsx")
    mock_s3.put_object.assert_called_once()
    call_kwargs = mock_s3.put_object.call_args[1]
    assert call_kwargs["Bucket"] == "reports"

    # Verify SQL query used parameterized binding
    call_args = mock_read_sql.call_args
    sql_text = str(call_args[0][0])
    params = call_args[1]["params"]
    assert "uploaded_by = :uploaded_by" in sql_text
    assert "status_id = :status_id" in sql_text
    assert "currency = :currency" in sql_text
    assert "issue_date >= :date_from" in sql_text
    assert "LIMIT :limit" in sql_text
    assert params["uploaded_by"] == 10
    assert params["status_id"] == 2
    assert params["currency"] == "PLN"
    assert params["limit"] == 500


def test_generate_invoices_report_invalid_dates():
    mock_engine = MagicMock()
    mock_s3 = MagicMock()

    with pytest.raises(ValueError, match="date_from nie może być późniejsza niż date_to"):
        generate_invoices_report(
            engine=mock_engine,
            s3_client=mock_s3,
            date_from=date(2026, 5, 1),
            date_to=date(2026, 4, 1),
        )


def test_post_invoices_report_endpoint():
    client = TestClient(app)

    mock_result = {
        "file_path": "invoices/raport_faktury_20261011_test.xlsx",
        "bucket": "reports",
        "filename": "raport_faktury_20261011_test.xlsx",
        "download_url": "http://localhost:9000/reports/invoices/raport_faktury_20261011_test.xlsx",
        "rows_count": 5,
        "generated_at": "2026-10-11T15:00:00",
    }

    mock_engine = MagicMock()
    mock_s3 = MagicMock()

    app.dependency_overrides[get_db_engine] = lambda: mock_engine
    app.dependency_overrides[get_s3_client] = lambda: mock_s3

    with patch("routers.reports.generate_invoices_report", return_value=mock_result):
        payload = {
            "date_from": "2026-01-01",
            "date_to": "2026-10-11",
            "status_id": 3,
            "uploaded_by": 42,
        }
        response = client.post("/api/v1/reports/invoices", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["file_path"] == "invoices/raport_faktury_20261011_test.xlsx"
        assert data["bucket"] == "reports"
        assert data["rows_count"] == 5

    app.dependency_overrides.clear()


def test_post_invoices_report_invalid_date_range():
    client = TestClient(app)

    mock_engine = MagicMock()
    mock_s3 = MagicMock()

    app.dependency_overrides[get_db_engine] = lambda: mock_engine
    app.dependency_overrides[get_s3_client] = lambda: mock_s3

    payload = {
        "date_from": "2026-10-15",
        "date_to": "2026-10-01",
    }
    response = client.post("/api/v1/reports/invoices", json=payload)
    assert response.status_code == 400

    app.dependency_overrides.clear()


def test_get_invoices_report_endpoint():
    client = TestClient(app)

    mock_result = {
        "file_path": "invoices/raport_faktury_get.xlsx",
        "bucket": "reports",
        "filename": "raport_faktury_get.xlsx",
        "download_url": "http://localhost:9000/reports/invoices/raport_faktury_get.xlsx",
        "rows_count": 0,
        "generated_at": "2026-10-11T15:00:00",
    }

    mock_engine = MagicMock()
    mock_s3 = MagicMock()

    app.dependency_overrides[get_db_engine] = lambda: mock_engine
    app.dependency_overrides[get_s3_client] = lambda: mock_s3

    with patch("routers.reports.generate_invoices_report", return_value=mock_result):
        response = client.get("/api/v1/reports/invoices?status_id=1&currency=EUR")
        assert response.status_code == 200
        data = response.json()
        assert data["file_path"] == "invoices/raport_faktury_get.xlsx"
        assert data["bucket"] == "reports"
        assert data["rows_count"] == 0

    app.dependency_overrides.clear()
