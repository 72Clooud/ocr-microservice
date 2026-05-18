from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "OCR Worker API"

    MINIO_ROOT_USER: str
    MINIO_ROOT_PASSWORD: str
    MINIO_INTERNAL_ENDPOINT: str
    MINIO_EXTERNAL_URL: str
    BUCKET_NAME: str
    
    OLLAMA_HOST: str

    class Config:
        env_file = ".env"

settings = Settings()