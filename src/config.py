from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    PROJECT_NAME: str = "OCR Worker"

    MINIO_ROOT_USER: str
    MINIO_ROOT_PASSWORD: str
    MINIO_INTERNAL_ENDPOINT: str
    MINIO_EXTERNAL_URL: str
    BUCKET_NAME: str
    
    OLLAMA_HOST: str
    
    REDIS_PASSWORD: str
    REDIS_HOST: str = "redis"
    REDIS_PORT: str = "6379"
    
    WEBHOOK_SECRET_TOKEN: str

    @property
    def CELERY_BROKER_URL(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/0"

settings = Settings()