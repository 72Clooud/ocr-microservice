from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    PROJECT_NAME: str = "OCR Worker"

    # Azure Blob Storage
    AZURE_STORAGE_CONNECTION_STRING: str
    AZURE_STORAGE_CONTAINER_NAME: str = "invoices"

    OLLAMA_HOST: str
    
    REDIS_PASSWORD: str
    REDIS_HOST: str = "redis"
    REDIS_PORT: str = "6379"
    REDIS_SSL: bool = False
    
    WEBHOOK_SECRET_TOKEN: str

    @property
    def CELERY_BROKER_URL(self) -> str:
        scheme = "rediss" if self.REDIS_SSL else "redis"
        ssl_params = "?ssl_cert_reqs=none" if self.REDIS_SSL else ""
        return f"{scheme}://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/0{ssl_params}"

settings = Settings()