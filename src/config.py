from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    PROJECT_NAME: str = "OCR Worker"

    MINIO_ROOT_USER: str | None = None
    MINIO_ROOT_PASSWORD: str | None = None
    MINIO_INTERNAL_ENDPOINT: str | None = None
    MINIO_EXTERNAL_URL: str | None = None
    BUCKET_NAME: str | None = None

    AZURE_STORAGE_CONNECTION_STRING: str | None = None
    AZURE_CONTAINER_NAME: str | None = None

    LLM_API_BASE_URL: str
    
    REDIS_PASSWORD: str
    REDIS_HOST: str = "redis"
    REDIS_PORT: str = "6379"
    REDIS_SSL: bool = False

    RUNPOD_API_KEY: str | None = None
    RUNPOD_POD_ID: str | None = None
    RUNPOD_NETWORK_VOLUME_ID: str | None = None
    RUNPOD_TEMPLATE_ID: str | None = None
    RUNPOD_AUTO_LIFECYCLE: bool = False
    RUNPOD_IDLE_TIMEOUT_SECONDS: int = 300

    @property
    def CELERY_BROKER_URL(self) -> str:
        scheme = "rediss" if self.REDIS_SSL else "redis"
        ssl_params = "?ssl_cert_reqs=none" if self.REDIS_SSL else ""
        return f"{scheme}://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/0{ssl_params}"

settings = Settings()
