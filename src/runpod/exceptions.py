class RunPodError(Exception):
    """Base exception for all RunPod operations."""


class RunPodAPIError(RunPodError):
    """Raised when an HTTP request to the RunPod REST API fails."""

    def __init__(self, message: str, status_code: int | None = None, response_text: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class InsufficientGPUCapacityError(RunPodError):
    """Raised when the host machine or datacenter does not have available GPUs."""


class PodTimeoutError(RunPodError):
    """Raised when a pod fails to report readiness within the allotted timeout."""
