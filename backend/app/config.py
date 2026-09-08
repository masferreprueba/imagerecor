from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Mas Ferre Image Processor"
    app_env: str = "development"
    cors_origins: str = "http://localhost:3000,http://localhost:4173"
    image_api_provider: str = "claid"
    image_api_key: str = ""
    image_api_timeout: int = 90
    image_api_max_retries: int = 3
    output_size: int = 500
    object_margin_percent: int = 10
    max_upload_mb: int = 250
    max_files_per_zip: int = 2000
    max_uncompressed_mb: int = 1500
    max_compression_ratio: int = 100
    processing_concurrency: int = 1
    task_queue: str = "inline"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"
    database_url: str = "sqlite:///./data/app.db"
    storage_root: Path = Path("./data/jobs")
    temp_ttl_hours: int = 24

    @property
    def allowed_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
