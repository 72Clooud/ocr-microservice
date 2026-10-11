import logging

from fastapi import APIRouter, Depends, HTTPException
from dependencies import get_runpod_service
from runpod import RunPodService, RunPodError
from schemas import PodStatusResponse, PodActionResponse

router = APIRouter(prefix="/api/v1/pod", tags=["RunPod"])
logger = logging.getLogger(__name__)


@router.get("/status", response_model=PodStatusResponse)
async def get_pod_status(service: RunPodService = Depends(get_runpod_service)):
    try:
        return service.get_status()
    except (RunPodError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/start", response_model=PodActionResponse)
async def start_pod(service: RunPodService = Depends(get_runpod_service)):
    try:
        return service.start_pod()
    except (RunPodError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/stop", response_model=PodActionResponse)
async def stop_pod(service: RunPodService = Depends(get_runpod_service)):
    try:
        return service.stop_pod()
    except (RunPodError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=str(exc))