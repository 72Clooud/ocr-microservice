import logging
from typing import Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from .exceptions import (
    RunPodAPIError,
    InsufficientGPUCapacityError,
)

logger = logging.getLogger(__name__)


class RunPodClient:
    DEFAULT_BASE_URL = "https://rest.runpod.io/v1"
    DEFAULT_TIMEOUT = (5.0, 30.0)
    HEALTH_URL_TEMPLATE = "https://{pod_id}-8080.proxy.runpod.net/health"

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ):
        if not api_key:
            raise ValueError("RunPod API key is required.")

        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 502, 503, 504],
            allowed_methods=["GET", "POST", "DELETE"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        kwargs.setdefault("timeout", self.DEFAULT_TIMEOUT)
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            response = self.session.request(method, url, **kwargs)
        except requests.RequestException as exc:
            raise RunPodAPIError(f"HTTP request failed: {exc}") from exc

        if response.status_code == 404:
            return None

        # Detect specific capacity errors
        if response.status_code in (400, 500):
            text = response.text.lower()
            if "not enough free gpus" in text or "no instances currently available" in text:
                raise InsufficientGPUCapacityError(
                    f"GPU capacity unavailable: {response.text}"
                )

        if not response.ok:
            raise RunPodAPIError(
                message=f"RunPod API error ({response.status_code}): {response.text}",
                status_code=response.status_code,
                response_text=response.text,
            )

        if response.status_code == 204 or not response.content:
            return None

        try:
            return response.json()
        except ValueError as exc:
            raise RunPodAPIError(f"Invalid JSON response: {exc}") from exc

    def get_pod(self, pod_id: str) -> dict | None:
        return self._request("GET", f"/pods/{pod_id}")

    def start_pod(self, pod_id: str) -> None:
        self._request("POST", f"/pods/{pod_id}/start")

    def stop_pod(self, pod_id: str) -> None:
        self._request("POST", f"/pods/{pod_id}/stop")

    def terminate_pod(self, pod_id: str) -> None:
        self._request("DELETE", f"/pods/{pod_id}")

    def create_pod(self, payload: dict) -> dict:
        result = self._request("POST", "/pods", json=payload)
        if not result or "id" not in result:
            raise RunPodAPIError(f"Unexpected response when creating pod: {result}")
        return result

    def is_health_ready(self, pod_id: str, timeout: float = 3.0) -> bool:
        url = self.HEALTH_URL_TEMPLATE.format(pod_id=pod_id)
        try:
            resp = self.session.get(url, timeout=timeout)
            return resp.status_code == 200
        except Exception:
            return False
