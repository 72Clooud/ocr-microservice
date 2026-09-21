from typing import List

REDIS_POD_ID_KEY = "runpod:current_pod_id"

RUNPOD_API_BASE_URL = "https://api.runpod.io/v2"
DEFAULT_TIMEOUT = (5.0, 30.0)

HEALTH_URL_TEMPLATE = "https://{pod_id}-8080.proxy.runpod.net/health"
LLM_URL_TEMPLATE = "https://{pod_id}-8080.proxy.runpod.net/v1"
