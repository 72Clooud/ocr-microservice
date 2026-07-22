import io
from unittest.mock import patch, MagicMock
from PIL import Image
import pytest
import requests
from celery.exceptions import Retry

from tasks import (
    _clean_extracted_data,
    _send_webhook,
    process_invoice_task,
)


def test_clean_extracted_data():
    # Test JSON code block with newline and json label
    data1 = "```json\n{\n  \"invoice_number\": \"INV-123\"\n}\n```"
    assert _clean_extracted_data(data1) == '{\n  "invoice_number": "INV-123"\n}'

    # Test plain code block
    data2 = "```\n{\n  \"invoice_number\": \"INV-123\"\n}\n```"
    assert _clean_extracted_data(data2) == '{\n  "invoice_number": "INV-123"\n}'

    # Test no code blocks, but leading/trailing whitespace
    data3 = "   {\n  \"invoice_number\": \"INV-123\"\n}  "
    assert _clean_extracted_data(data3) == '{\n  "invoice_number": "INV-123"\n}'


@patch("tasks.requests.post")
def test_send_webhook_success(mock_post):
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    payload = {"task_id": "test-task", "status": "SUCCESS"}
    _send_webhook("http://example.com/webhook", payload, "test-task")

    mock_post.assert_called_once_with(
        "http://example.com/webhook", json=payload, timeout=10
    )


@patch("tasks.requests.post")
def test_send_webhook_failure(mock_post):
    mock_post.side_effect = requests.RequestException("Connection failed")

    payload = {"task_id": "test-task", "status": "SUCCESS"}
    with pytest.raises(requests.RequestException):
        _send_webhook("http://example.com/webhook", payload, "test-task")


def _generate_test_image(width: int, height: int) -> bytes:
    img = Image.new("RGB", (width, height), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@patch("tasks.s3_client.get_object")
@patch("tasks.ollama_client.chat")
@patch("tasks.requests.post")
def test_process_invoice_task_success(mock_post, mock_ollama_chat, mock_s3_get_object):
    # Setup: S3 returns a large image to test resizing logic
    large_image_bytes = _generate_test_image(2000, 1000)
    mock_body = MagicMock()
    mock_body.read.return_value = large_image_bytes
    mock_s3_get_object.return_value = {"Body": mock_body}

    # Setup: Ollama returns a simulated model response containing JSON
    mock_ollama_chat.return_value = {
        "message": {
            "content": "```json\n"
                       "{\n"
                       "  \"invoice_number\": \"INV-999\",\n"
                       "  \"seller\": {\n"
                       "    \"name\": \"ACME Corp\"\n"
                       "  }\n"
                       "}\n"
                       "```"
        }
    }

    # Setup: Webhook request returns success
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    # Run the task (with Celery binding bypassed, or running directly as function)
    result = process_invoice_task("task-uuid-1", "path/to/invoice.jpg", "http://webhook")

    assert result is True

    # Verify S3 call
    mock_s3_get_object.assert_called_once_with(Bucket="test-bucket", Key="path/to/invoice.jpg")

    # Verify Ollama chat parameters
    mock_ollama_chat.assert_called_once()
    called_args, called_kwargs = mock_ollama_chat.call_args
    assert called_kwargs["model"] == "glm-ocr:q8_0"
    assert called_kwargs["options"] == {"num_ctx": 4096}
    assert len(called_kwargs["messages"]) == 1
    assert called_kwargs["messages"][0]["role"] == "user"
    assert "images" in called_kwargs["messages"][0]

    # Verify Webhook call
    mock_post.assert_called_once()
    called_webhook_url, called_webhook_kwargs = mock_post.call_args
    assert called_webhook_url[0] == "http://webhook"
    
    sent_payload = called_webhook_kwargs["json"]
    assert sent_payload["task_id"] == "task-uuid-1"
    assert sent_payload["status"] == "SUCCESS"
    assert sent_payload["data"]["invoice_number"] == "INV-999"
    assert sent_payload["data"]["seller"]["name"] == "ACME Corp"


@patch("tasks.s3_client.get_object")
@patch("tasks.process_invoice_task.retry")
def test_process_invoice_task_s3_failure(mock_retry, mock_s3_get_object):
    # Setup: S3 throws an exception
    exc = Exception("MinIO offline")
    mock_s3_get_object.side_effect = exc
    mock_retry.side_effect = Retry()

    with pytest.raises(Retry):
        process_invoice_task("task-uuid-2", "path/to/invoice.jpg", "http://webhook")

    mock_retry.assert_called_once_with(exc=exc, countdown=60)


@patch("tasks.s3_client.get_object")
@patch("tasks.ollama_client.chat")
@patch("tasks.process_invoice_task.retry")
def test_process_invoice_task_ollama_failure(mock_retry, mock_ollama_chat, mock_s3_get_object):
    # Setup: S3 returns a valid image
    image_bytes = _generate_test_image(100, 100)
    mock_body = MagicMock()
    mock_body.read.return_value = image_bytes
    mock_s3_get_object.return_value = {"Body": mock_body}

    # Setup: Ollama client throws an exception
    exc = Exception("Ollama client connection refused")
    mock_ollama_chat.side_effect = exc
    mock_retry.side_effect = Retry()

    with pytest.raises(Retry):
        process_invoice_task("task-uuid-3", "path/to/invoice.jpg", "http://webhook")

    mock_retry.assert_called_once_with(exc=exc, countdown=60)
