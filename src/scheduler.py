import logging

from tasks import celery_app
from dependencies import get_runpod_service
from runpod import RunPodError

logger = logging.getLogger(__name__)


@celery_app.task(name="scheduled_pod_start")
def scheduled_pod_start():
    try:
        service = get_runpod_service()
        llm_url = service.start_pod()
        logger.info(f"[Scheduler] Pod started, LLM URL: {llm_url}")
    except RunPodError as exc:
        logger.error(f"[Scheduler] Failed to start pod: {exc}")


@celery_app.task(name="scheduled_pod_stop")
def scheduled_pod_stop():
    try:
        service = get_runpod_service()
        service.stop_pod()
        logger.info("[Scheduler] Pod stopped")
    except RunPodError as exc:
        logger.error(f"[Scheduler] Failed to stop pod: {exc}")
