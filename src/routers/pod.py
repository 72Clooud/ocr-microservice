import logging

from fastapi import APIRouter, Depends, HTTPException
from dependencies import get_runpod_service
from runpod import RunPodService, RunPodError

router = APIRouter(prefix="/api/v1/pod", tags=["RunPod"])
logger = logging.getLogger(__name__)


@router.get("/status")
async def get_pod_status(service: RunPodService = Depends(get_runpod_service)):
    try:
        return service.get_status()
    except RunPodError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/start")
async def start_pod(service: RunPodService = Depends(get_runpod_service)):
    try:
        llm_url = service.start_pod()
        return {"message": "Pod started", "pod_id": service.pod_id, "llm_url": llm_url}
    except RunPodError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/stop")
async def stop_pod(service: RunPodService = Depends(get_runpod_service)):
    try:
        service.stop_pod()
        return {"message": "Pod stopped", "pod_id": service.pod_id}
    except RunPodError as exc:
        raise HTTPException(status_code=502, detail=str(exc))