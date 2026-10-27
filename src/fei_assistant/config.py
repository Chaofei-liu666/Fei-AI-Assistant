from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="FEI_", extra="ignore"
    )

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    database_url: str = "postgresql+psycopg://fei:fei-local@127.0.0.1:5432/fei"
    minio_endpoint: str = "http://127.0.0.1:9000"
    minio_access_key: str = "fei-local"
    minio_secret_key: str = "change-me-local-only"
    minio_bucket: str = "fei-private"
    minio_secure: bool = False
    max_upload_mb: int = 100


@lru_cache
def get_settings() -> Settings:
    return Settings()
