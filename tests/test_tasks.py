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

    # Test conversational text before code block
    data4 = "Here is the extracted invoice JSON:\n```json\n{\n  \"invoice_number\": \"INV-123\"\n}\n```\nHope this helps!"
    assert _clean_extracted_data(data4) == '{\n  "invoice_number": "INV-123"\n}'

    # Test raw json surrounded by conversational text without code blocks
    data5 = "Sure! {\"invoice_number\": \"INV-123\"} is the output."
    assert _clean_extracted_data(data5) == '{"invoice_number": "INV-123"}'


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


@patch("tasks.blob_service_client")
@patch("tasks.llm_client.chat.completions.create")
@patch("tasks.requests.post")
@patch("tasks.settings")
def test_process_invoice_task_success(mock_settings, mock_post, mock_llm_chat, mock_blob_client):
    # Setup: Settings
    mock_settings.AZURE_CONTAINER_NAME = "test-container"
    mock_settings.AZURE_STORAGE_CONNECTION_STRING = "mock"
    
    # Setup: Azure returns a large image to test resizing logic
    large_image_bytes = _generate_test_image(2000, 1000)
    mock_blob_instance = MagicMock()
    mock_blob_instance.download_blob.return_value.readall.return_value = large_image_bytes
    mock_blob_client.get_blob_client.return_value = mock_blob_instance

    # Setup: OpenAI returns a simulated model response containing JSON
    mock_choice = MagicMock()
    mock_choice.message.content = "```json\n" \
                                   "{\n" \
                                   "  \"invoice_number\": \"INV-999\",\n" \
                                   "  \"seller\": {\n" \
                                   "    \"name\": \"ACME Corp\"\n" \
                                   "  }\n" \
                                   "}\n" \
                                   "```"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_llm_chat.return_value = mock_response

    # Setup: Webhook request returns success
    mock_webhook_response = MagicMock()
    mock_webhook_response.raise_for_status.return_value = None
    mock_post.return_value = mock_webhook_response

    # Run the task
    result = process_invoice_task("task-uuid-1", "path/to/invoice.jpg", "http://webhook")

    assert result is True

    # Verify Azure call
    mock_blob_client.get_blob_client.assert_called_once_with(container="test-container", blob="path/to/invoice.jpg")

    # Verify LLM chat parameters
    mock_llm_chat.assert_called_once()
    called_kwargs = mock_llm_chat.call_args[1]
    assert called_kwargs["model"] == "glm-ocr"
    assert called_kwargs["response_format"] == {"type": "json_object"}
    assert called_kwargs["temperature"] == 0.0

    # Verify Webhook call
    mock_post.assert_called_once()
    called_webhook_url, called_webhook_kwargs = mock_post.call_args
    assert called_webhook_url[0] == "http://webhook"
    
    sent_payload = called_webhook_kwargs["json"]
    assert sent_payload["task_id"] == "task-uuid-1"
    assert sent_payload["data"]["invoice_number"] == "INV-999"
    assert sent_payload["data"]["seller"]["name"] == "ACME Corp"


@patch("tasks.blob_service_client")
@patch("tasks.process_invoice_task.retry")
@patch("tasks.settings")
def test_process_invoice_task_storage_failure(mock_settings, mock_retry, mock_blob_client):
    mock_settings.AZURE_CONTAINER_NAME = "test-container"
    mock_settings.AZURE_STORAGE_CONNECTION_STRING = "mock"
    
    # Setup: Azure throws an exception
    exc = Exception("Storage offline")
    mock_blob_client.get_blob_client.side_effect = exc
    mock_retry.side_effect = Retry()

    with pytest.raises(Retry):
        process_invoice_task("task-uuid-2", "path/to/invoice.jpg", "http://webhook")

    mock_retry.assert_called_once_with(exc=exc, countdown=60)


@patch("tasks.blob_service_client")
@patch("tasks.llm_client.chat.completions.create")
@patch("tasks.process_invoice_task.retry")
@patch("tasks.settings")
def test_process_invoice_task_llm_failure(mock_settings, mock_retry, mock_llm_chat, mock_blob_client):
    mock_settings.AZURE_CONTAINER_NAME = "test-container"
    mock_settings.AZURE_STORAGE_CONNECTION_STRING = "mock"
    
    image_bytes = _generate_test_image(100, 100)
    mock_blob_instance = MagicMock()
    mock_blob_instance.download_blob.return_value.readall.return_value = image_bytes
    mock_blob_client.get_blob_client.return_value = mock_blob_instance

    # Setup: LLM client throws an exception
    exc = Exception("LLM client connection refused")
    mock_llm_chat.side_effect = exc
    mock_retry.side_effect = Retry()

    with pytest.raises(Retry):
        process_invoice_task("task-uuid-3", "path/to/invoice.jpg", "http://webhook")

    mock_retry.assert_called_once_with(exc=exc, countdown=60)
