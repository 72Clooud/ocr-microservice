import logging

from fastapi import FastAPI

from config import settings
from routers import invoices, pod

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.PROJECT_NAME)
app.include_router(invoices.router)
app.include_router(pod.router)
