import logging
from typing import List, Optional

import redis

from config import settings
from .client import RunPodClient
from .exceptions import (
    RunPodError,
    RunPodAPIError,
    InsufficientGPUCapacityError,
)
from .constants import (
    REDIS_POD_ID_KEY,
    LLM_URL_TEMPLATE,
)

logger = logging.getLogger(__name__)


class RunPodService:
    def __init__(
        self,
        redis_client: redis.Redis,
        api_key: Optional[str] = None,
        template_id: Optional[str] = None,
        client: Optional[RunPodClient] = None,
    ):
        self.api_key = api_key or settings.RUNPOD_API_KEY
        self.template_id = template_id or settings.RUNPOD_TEMPLATE_ID

        if not self.api_key:
            raise ValueError("RUNPOD_API_KEY is not configured in environment or settings.")

        self.client = client or RunPodClient(api_key=self.api_key)
        self._redis = redis_client

    @property
    def pod_id(self) -> Optional[str]:
        return self._redis.get(REDIS_POD_ID_KEY)

    @pod_id.setter
    def pod_id(self, value: str) -> None:
        self._redis.set(REDIS_POD_ID_KEY, value)
        logger.info(f"[RunPod] Pod ID updated in Redis: {value}")

    @property
    def model_base_url(self) -> Optional[str]:
        pid = self.pod_id
        return LLM_URL_TEMPLATE.format(pod_id=pid) if pid else None

    def is_pod_ready(self, timeout: float = 3.0) -> bool:
        pid = self.pod_id
        if not pid:
            return False
        return self.client.is_health_ready(pod_id=pid, timeout=timeout)

    def get_status(self) -> dict:
        pid = self.pod_id
        if not pid:
            return {"configured": False, "error": "No pod_id configured"}

        info = self.client.get_pod(pid)
        ready = self.is_pod_ready()
        return {
            "configured": True,
            "pod_id": pid,
            "llm_url": self.model_base_url,
            "health_ready": ready,
            "pod_info": info,
        }

    def create_budget_pod(self) -> dict:
        logger.info("[RunPod] Fetching available GPUs from catalog...")
        available_gpus = self.client.get_available_gpus()
        if not available_gpus:
            raise RunPodError("No GPUs currently available in the RunPod catalog.")
        
        available_gpus.sort(key=lambda g: g.get("price", {}).get("secure", float('inf')))
        target_gpus = [g["id"] for g in available_gpus]
        
        logger.info(f"[RunPod] Found {len(target_gpus)} available GPU types. Cheapest is {target_gpus[0]}.")
        
        if not self.template_id:
            raise RunPodError("RUNPOD_TEMPLATE_ID must be configured to create a pod.")

        base_payload = {
            "name": "ocr-llama-server",
            "templateId": self.template_id,
            "ports": ["8080/http", "22/tcp"],
        }

        logger.info("[RunPod] Provisioning budget pod (v2 API)...")
        
        for gpu_id in target_gpus:
            payload = dict(base_payload)
            payload["gpu"] = {"id": gpu_id, "count": 1}
            
            try:
                pod_data = self.client.create_pod(payload)
                new_id = pod_data["id"]
                self.pod_id = new_id 
                logger.info(f"[RunPod] Created pod {new_id} with GPU {gpu_id}")
                return pod_data
            except InsufficientGPUCapacityError:
                logger.info(f"[RunPod] GPU {gpu_id} out of capacity despite catalog availability, trying next...")
                continue
            except RunPodAPIError as exc:
                if exc.status_code in (400, 403):
                    logger.info(f"[RunPod] GPU {gpu_id} unavailable (HTTP {exc.status_code}), trying next...")
                    continue
                raise

        raise RunPodError("Failed to provision pod: No capacity or access for any of the budget GPUs.")

    def start_pod(self) -> str:
        pid = self.pod_id
        if not pid:
            raise ValueError("No pod_id configured.")

        if self.is_pod_ready(timeout=2.0):
            logger.info(f"[RunPod] Pod {pid} is already running.")
            return self.model_base_url

        existing_pod = None
        try:
            existing_pod = self.client.get_pod(pid)
        except RunPodAPIError as exc:
            logger.warning(f"[RunPod] Could not query pod {pid}: {exc}")

        if existing_pod:
            try:
                self.client.start_pod(pid)
                logger.info(f"[RunPod] Start requested for pod {pid}")
            except InsufficientGPUCapacityError:
                logger.warning("[RunPod] No GPU available, creating new pod...")
                self.client.terminate_pod(pid)
                self.create_budget_pod()
        else:
            self.create_budget_pod()

        return self.model_base_url

    def stop_pod(self) -> None:
        pid = self.pod_id
        if not pid:
            logger.warning("[RunPod] No pod_id configured.")
            return
        self.client.stop_pod(pid)
        logger.info(f"[RunPod] Pod {pid} stopped.")

    def terminate_pod(self) -> None:
        pid = self.pod_id
        if not pid:
            return
        self.client.terminate_pod(pid)
        logger.info(f"[RunPod] Pod {pid} terminated.")
