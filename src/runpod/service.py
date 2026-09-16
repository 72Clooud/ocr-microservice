import logging
import re
import time
from pathlib import Path
from typing import List, Optional

from config import settings
from .client import RunPodClient
from .exceptions import (
    RunPodError,
    RunPodAPIError,
    InsufficientGPUCapacityError,
    PodTimeoutError,
)

logger = logging.getLogger(__name__)

DEFAULT_BUDGET_GPUS: List[str] = [
    "NVIDIA RTX 2000 Ada Generation",
    "NVIDIA GeForce RTX 3070",
    "NVIDIA GeForce RTX 3080",
    "NVIDIA RTX A4000",
    "NVIDIA RTX 4000 SFF Ada Generation",
    "NVIDIA GeForce RTX 4070 Ti",
    "NVIDIA RTX A4500",
    "NVIDIA GeForce RTX 3090",
]


class RunPodService:
    LLM_URL_TEMPLATE = "https://{pod_id}-8080.proxy.runpod.net/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        pod_id: Optional[str] = None,
        network_volume_id: Optional[str] = None,
        template_id: Optional[str] = None,
        client: Optional[RunPodClient] = None,
    ):
        self.api_key = api_key or settings.RUNPOD_API_KEY
        self.pod_id = pod_id or settings.RUNPOD_POD_ID
        self.network_volume_id = network_volume_id or settings.RUNPOD_NETWORK_VOLUME_ID
        self.template_id = template_id or settings.RUNPOD_TEMPLATE_ID

        if not self.api_key:
            raise ValueError("RUNPOD_API_KEY is not configured in environment or settings.")

        self.client = client or RunPodClient(api_key=self.api_key)

    def get_llm_base_url(self, pod_id: Optional[str] = None) -> Optional[str]:
        target = pod_id or self.pod_id
        return self.LLM_URL_TEMPLATE.format(pod_id=target) if target else None

    def is_pod_ready(self, pod_id: Optional[str] = None, timeout: float = 3.0) -> bool:
        target = pod_id or self.pod_id
        if not target:
            return False
        return self.client.is_health_ready(pod_id=target, timeout=timeout)

    def get_status(self) -> dict:
        if not self.pod_id:
            return {"configured": False, "error": "No RUNPOD_POD_ID configured"}

        info = self.client.get_pod(self.pod_id)
        ready = self.is_pod_ready()
        return {
            "configured": True,
            "pod_id": self.pod_id,
            "llm_url": self.get_llm_base_url(),
            "health_ready": ready,
            "pod_info": info,
        }

    def wait_for_ready(self, pod_id: Optional[str] = None, timeout_seconds: int = 240, poll_interval: float = 3.0) -> float:
        target = pod_id or self.pod_id
        if not target:
            raise ValueError("Cannot wait for readiness without a pod_id.")

        logger.info(f"[RunPod] Waiting for model readiness for pod {target}...")
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            if self.client.is_health_ready(target, timeout=3.0):
                elapsed = time.time() - start_time
                logger.info(f"[RunPod] Pod {target} is READY! Boot time: {elapsed:.2f}s")
                return elapsed
            time.sleep(poll_interval)

        elapsed = time.time() - start_time
        raise PodTimeoutError(f"Pod {target} failed to become ready within {elapsed:.1f}s.")

    def create_budget_pod(self, gpu_types: Optional[List[str]] = None) -> dict:
        payload = {
            "name": "ocr-llama-server",
            "computeType": "GPU",
            "gpuCount": 1,
            "gpuTypeIds": gpu_types or DEFAULT_BUDGET_GPUS,
            "ports": ["8080/http", "22/tcp"],
            "supportPublicIp": True,
        }

        if self.template_id:
            payload["templateId"] = self.template_id
        else:
            payload["imageName"] = "ghcr.io/ggml-org/llama.cpp:server-cuda"
            payload["dockerStartCmd"] = [
                "-m", "/workspace/models/glm-ocr-q8_0.gguf",
                "--mmproj", "/workspace/models/mmproj-glm-ocr.gguf",
                "--host", "0.0.0.0",
                "--port", "8080",
                "-c", "8192",
                "-cb",
                "-ngl", "999",
            ]

        if self.network_volume_id:
            payload["networkVolumeId"] = self.network_volume_id
            payload["volumeMountPath"] = "/workspace"

        logger.info(f"[RunPod] Provisioning fresh budget pod with network volume {self.network_volume_id}...")
        pod_data = self.client.create_pod(payload)
        new_id = pod_data["id"]
        self.pod_id = new_id
        logger.info(f"[RunPod] Successfully created new pod {new_id}")
        return pod_data

    def sync_env_file(self, new_pod_id: str):
        candidates = [Path(".env"), Path("../.env")]
        target_file = None
        for candidate in candidates:
            if candidate.exists():
                target_file = candidate
                break

        if not target_file:
            return

        new_llm_url = self.get_llm_base_url(new_pod_id)
        try:
            content = target_file.read_text(encoding="utf-8")
            if "RUNPOD_POD_ID" in content:
                content = re.sub(r'RUNPOD_POD_ID=.*', f'RUNPOD_POD_ID="{new_pod_id}"', content)
            else:
                content += f'\nRUNPOD_POD_ID="{new_pod_id}"'

            if "LLM_API_BASE_URL" in content:
                content = re.sub(r'LLM_API_BASE_URL=.*', f'LLM_API_BASE_URL="{new_llm_url}"', content)
            else:
                content += f'\nLLM_API_BASE_URL="{new_llm_url}"'

            target_file.write_text(content, encoding="utf-8")
            logger.info(f"[RunPod] Updated {target_file} with new pod ID {new_pod_id}")
        except Exception as exc:
            logger.warning(f"[RunPod] Could not update .env file: {exc}")

    def morning_startup(self) -> str:
        logger.info("[RunPod] Running morning startup sequence...")

        if self.is_pod_ready(timeout=2.0):
            logger.info(f"[RunPod] Pod {self.pod_id} is already active and healthy.")
            return self.get_llm_base_url()

        existing_pod = None
        if self.pod_id:
            try:
                existing_pod = self.client.get_pod(self.pod_id)
            except RunPodAPIError as exc:
                logger.warning(f"[RunPod] Could not query pod {self.pod_id}: {exc}")

        resumed = False
        if existing_pod:
            status = existing_pod.get("desiredStatus")
            logger.info(f"[RunPod] Existing pod {self.pod_id} found (status: {status}). Attempting to start...")
            try:
                self.client.start_pod(self.pod_id)
                resumed = True
            except InsufficientGPUCapacityError as exc:
                logger.warning(f"[RunPod] Cannot resume existing pod (no GPU on host): {exc}")
                logger.info(f"[RunPod] Cleaning up unresumable pod {self.pod_id}...")
                self.client.terminate_pod(self.pod_id)
            except RunPodAPIError as exc:
                logger.warning(f"[RunPod] Error starting existing pod: {exc}")

        if not resumed:
            logger.info("[RunPod] Provisioning a fresh pod on an available GPU host...")
            new_pod = self.create_budget_pod()
            new_id = new_pod["id"]
            self.sync_env_file(new_id)

        self.wait_for_ready()
        llm_url = self.get_llm_base_url()
        logger.info(f"[RunPod] OCR LLM Server is online at: {llm_url}")
        return llm_url

    def evening_shutdown(self) -> None:
        if not self.pod_id:
            logger.warning("[RunPod] No pod_id configured to shut down.")
            return
        logger.info(f"[RunPod] Initiating evening shutdown for pod {self.pod_id}...")
        self.client.stop_pod(self.pod_id)
        logger.info(f"[RunPod] Pod {self.pod_id} successfully stopped.")

    def terminate_current_pod(self) -> None:
        if not self.pod_id:
            return
        logger.info(f"[RunPod] Terminating pod {self.pod_id}...")
        self.client.terminate_pod(self.pod_id)
        logger.info(f"[RunPod] Pod {self.pod_id} terminated.")
