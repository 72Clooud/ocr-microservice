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
    DEFAULT_POD_NAME,
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

    def discover_existing_pod(self, name: str = DEFAULT_POD_NAME) -> Optional[dict]:
        try:
            pods = self.client.list_pods()
        except RunPodError as exc:
            logger.warning(f"[RunPod] Could not list pods from API: {exc}")
            return None

        for pod in pods:
            if pod.get("name") == name and pod.get("status") != "TERMINATED":
                return pod
        return None

    @property
    def pod_id(self) -> Optional[str]:
        pid = self._redis.get(REDIS_POD_ID_KEY)
        if pid:
            return pid

        discovered = self.discover_existing_pod()
        if discovered:
            discovered_id = discovered["id"]
            self.pod_id = discovered_id
            logger.info(
                f"[RunPod] Discovered existing pod '{discovered.get('name')}' "
                f"({discovered_id}) on RunPod account. Cached to Redis."
            )
            return discovered_id

        return None

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
            return {
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

        info = self.client.get_pod(pid) or {}
        if not info or info.get("status") == "TERMINATED":
            logger.info(f"[RunPod] Pod {pid} is terminated or not found on RunPod. Clearing from Redis.")
            self._redis.delete(REDIS_POD_ID_KEY)
            discovered = self.discover_existing_pod()
            if discovered:
                pid = discovered["id"]
                self.pod_id = pid
                info = discovered
            else:
                return {
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

        runtime = info.get("runtime") or {}
        gpu_info = info.get("gpu") or {}

        return {
            "configured": True,
            "pod_id": pid,
            "status": info.get("status"),
            "health_ready": self.is_pod_ready(),
            "llm_url": self.model_base_url,
            "gpu": gpu_info.get("id"),
            "cost_per_hr": info.get("cost"),
            "started_at": info.get("startedAt"),
            "uptime_seconds": runtime.get("uptime"),
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
            "name": DEFAULT_POD_NAME,
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

    def start_pod(self) -> dict:
        pid = self.pod_id
        if not pid:
            logger.info("[RunPod] No pod in Redis or RunPod account. Provisioning fresh budget pod...")
            pod_data = self.create_budget_pod()
            return {
                "message": "Pod created and started",
                "pod_id": self.pod_id,
                "llm_url": self.model_base_url,
                "status": pod_data.get("status", "STARTING"),
            }

        existing_pod = None
        try:
            existing_pod = self.client.get_pod(pid)
        except RunPodAPIError as exc:
            logger.warning(f"[RunPod] Could not query pod {pid}: {exc}")

        if not existing_pod or existing_pod.get("status") == "TERMINATED":
            logger.info(f"[RunPod] Pod {pid} not found or terminated. Provisioning new budget pod...")
            self._redis.delete(REDIS_POD_ID_KEY)
            pod_data = self.create_budget_pod()
            return {
                "message": "Pod created and started",
                "pod_id": self.pod_id,
                "llm_url": self.model_base_url,
                "status": pod_data.get("status", "STARTING"),
            }

        current_status = existing_pod.get("status")

        if current_status == "RUNNING":
            logger.info(f"[RunPod] Pod {pid} is already running.")
            return {
                "message": "Pod is already running",
                "pod_id": pid,
                "llm_url": self.model_base_url,
                "status": "RUNNING",
            }

        if current_status in ("STARTING", "PROVISIONING"):
            logger.info(f"[RunPod] Pod {pid} is already {current_status.lower()}.")
            return {
                "message": f"Pod is already {current_status.lower()}",
                "pod_id": pid,
                "llm_url": self.model_base_url,
                "status": current_status,
            }

        try:
            self.client.start_pod(pid)
            logger.info(f"[RunPod] Start requested for pod {pid}")
            return {
                "message": "Pod started",
                "pod_id": pid,
                "llm_url": self.model_base_url,
                "status": "STARTING",
            }
        except InsufficientGPUCapacityError:
            logger.warning("[RunPod] No GPU available on current host, creating new pod...")
            self.client.terminate_pod(pid)
            pod_data = self.create_budget_pod()
            return {
                "message": "Pod recreated and started (new GPU host)",
                "pod_id": self.pod_id,
                "llm_url": self.model_base_url,
                "status": pod_data.get("status", "STARTING"),
            }

    def stop_pod(self) -> dict:
        pid = self.pod_id
        if not pid:
            logger.warning("[RunPod] No pod_id configured.")
            return {
                "message": "No pod configured",
                "pod_id": None,
                "status": None,
            }

        existing_pod = None
        try:
            existing_pod = self.client.get_pod(pid)
        except RunPodAPIError as exc:
            logger.warning(f"[RunPod] Could not query pod {pid}: {exc}")

        if not existing_pod or existing_pod.get("status") == "TERMINATED":
            self._redis.delete(REDIS_POD_ID_KEY)
            return {
                "message": "Pod not found or already terminated",
                "pod_id": pid,
                "status": "TERMINATED",
            }

        current_status = existing_pod.get("status")

        if current_status == "EXITED":
            logger.info(f"[RunPod] Pod {pid} is already stopped.")
            return {
                "message": "Pod is already stopped",
                "pod_id": pid,
                "status": "EXITED",
            }

        self.client.stop_pod(pid)
        logger.info(f"[RunPod] Pod {pid} stopped.")
        return {
            "message": "Pod stopped",
            "pod_id": pid,
            "status": "EXITED",
        }

    def terminate_pod(self) -> None:
        pid = self.pod_id
        if not pid:
            return
        self.client.terminate_pod(pid)
        self._redis.delete(REDIS_POD_ID_KEY)
        logger.info(f"[RunPod] Pod {pid} terminated and removed from Redis.")


