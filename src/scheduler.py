import logging

from tasks import celery_app
from dependencies import get_runpod_service
from runpod import RunPodError

logger = logging.getLogger(__name__)


@celery_app.task(name="scheduled_pod_start")
def scheduled_pod_start():
    try:
        service = get_runpod_service()
        result = service.start_pod()
        llm_url = result.get("llm_url") if isinstance(result, dict) else result
        logger.info(f"[Scheduler] Pod start result: {result.get('message') if isinstance(result, dict) else result}, LLM URL: {llm_url}")
    except RunPodError as exc:
        logger.error(f"[Scheduler] Failed to start pod: {exc}")


@celery_app.task(name="scheduled_pod_stop")
def scheduled_pod_stop():
    try:
        service = get_runpod_service()
        result = service.stop_pod()
        message = result.get("message") if isinstance(result, dict) else "Pod stopped"
        logger.info(f"[Scheduler] {message}")
    except RunPodError as exc:
        logger.error(f"[Scheduler] Failed to stop pod: {exc}")

