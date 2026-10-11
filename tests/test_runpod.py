from unittest.mock import MagicMock
import pytest

from runpod import RunPodService, RunPodClient
from runpod.constants import REDIS_POD_ID_KEY, DEFAULT_POD_NAME


def test_client_list_pods():
    client = RunPodClient(api_key="test-key")
    client._request = MagicMock(return_value={
        "pods": [
            {"id": "pod-1", "name": "ocr-llama-server", "status": "RUNNING"},
            {"id": "pod-2", "name": "other-pod", "status": "STOPPED"}
        ]
    })

    pods = client.list_pods()
    assert len(pods) == 2
    assert pods[0]["id"] == "pod-1"


def test_discover_existing_pod_found():
    redis_mock = MagicMock()
    redis_mock.get.return_value = None

    client_mock = MagicMock()
    client_mock.list_pods.return_value = [
        {"id": "pod-old", "name": DEFAULT_POD_NAME, "status": "TERMINATED"},
        {"id": "pod-active", "name": DEFAULT_POD_NAME, "status": "RUNNING"},
    ]

    service = RunPodService(
        redis_client=redis_mock,
        api_key="test-key",
        client=client_mock,
    )

    discovered = service.discover_existing_pod()
    assert discovered is not None
    assert discovered["id"] == "pod-active"


def test_pod_id_auto_discovery_when_redis_empty():
    redis_mock = MagicMock()
    redis_mock.get.return_value = None

    client_mock = MagicMock()
    client_mock.list_pods.return_value = [
        {"id": "pod-discovered-1", "name": DEFAULT_POD_NAME, "status": "RUNNING"}
    ]

    service = RunPodService(
        redis_client=redis_mock,
        api_key="test-key",
        client=client_mock,
    )

    # Calling service.pod_id should query list_pods and save to redis
    assert service.pod_id == "pod-discovered-1"
    redis_mock.set.assert_called_once_with(REDIS_POD_ID_KEY, "pod-discovered-1")


def test_pod_id_cached_in_redis():
    redis_mock = MagicMock()
    redis_mock.get.return_value = "pod-cached-123"

    client_mock = MagicMock()

    service = RunPodService(
        redis_client=redis_mock,
        api_key="test-key",
        client=client_mock,
    )

    assert service.pod_id == "pod-cached-123"
    client_mock.list_pods.assert_not_called()


def test_terminate_pod_clears_redis():
    redis_mock = MagicMock()
    redis_mock.get.return_value = "pod-to-kill"

    client_mock = MagicMock()

    service = RunPodService(
        redis_client=redis_mock,
        api_key="test-key",
        client=client_mock,
    )

    service.terminate_pod()
    client_mock.terminate_pod.assert_called_once_with("pod-to-kill")
    redis_mock.delete.assert_called_once_with(REDIS_POD_ID_KEY)


def test_start_pod_already_running():
    redis_mock = MagicMock()
    redis_mock.get.return_value = "pod-123"

    client_mock = MagicMock()
    client_mock.get_pod.return_value = {"id": "pod-123", "status": "RUNNING"}

    service = RunPodService(redis_client=redis_mock, api_key="test-key", client=client_mock)

    result = service.start_pod()
    assert result["message"] == "Pod is already running"
    assert result["status"] == "RUNNING"
    client_mock.start_pod.assert_not_called()


def test_start_pod_already_starting():
    redis_mock = MagicMock()
    redis_mock.get.return_value = "pod-123"

    client_mock = MagicMock()
    client_mock.get_pod.return_value = {"id": "pod-123", "status": "STARTING"}

    service = RunPodService(redis_client=redis_mock, api_key="test-key", client=client_mock)

    result = service.start_pod()
    assert result["message"] == "Pod is already starting"
    assert result["status"] == "STARTING"
    client_mock.start_pod.assert_not_called()


def test_start_pod_when_stopped():
    redis_mock = MagicMock()
    redis_mock.get.return_value = "pod-123"

    client_mock = MagicMock()
    client_mock.get_pod.return_value = {"id": "pod-123", "status": "EXITED"}

    service = RunPodService(redis_client=redis_mock, api_key="test-key", client=client_mock)

    result = service.start_pod()
    assert result["message"] == "Pod started"
    assert result["status"] == "STARTING"
    client_mock.start_pod.assert_called_once_with("pod-123")


def test_stop_pod_already_stopped():
    redis_mock = MagicMock()
    redis_mock.get.return_value = "pod-123"

    client_mock = MagicMock()
    client_mock.get_pod.return_value = {"id": "pod-123", "status": "EXITED"}

    service = RunPodService(redis_client=redis_mock, api_key="test-key", client=client_mock)

    result = service.stop_pod()
    assert result["message"] == "Pod is already stopped"
    assert result["status"] == "EXITED"
    client_mock.stop_pod.assert_not_called()


def test_stop_pod_when_running():
    redis_mock = MagicMock()
    redis_mock.get.return_value = "pod-123"

    client_mock = MagicMock()
    client_mock.get_pod.return_value = {"id": "pod-123", "status": "RUNNING"}

    service = RunPodService(redis_client=redis_mock, api_key="test-key", client=client_mock)

    result = service.stop_pod()
    assert result["message"] == "Pod stopped"
    assert result["status"] == "EXITED"
    client_mock.stop_pod.assert_called_once_with("pod-123")

