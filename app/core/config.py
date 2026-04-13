from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Doc Pipeline Phase 1.5"
    app_env: str = "dev"
    log_level: str = "INFO"

    docling_base_url: str = "http://localhost:5001"
    docling_api_key: str = ""
    docling_tenant_id: str = ""

    poll_wait_seconds: float = 2.0
    poll_interval_seconds: float = 1.0
    max_wait_seconds: float = 1200.0

    retry_max_attempts: int = 3
    retry_base_delay_ms: int = 500
    request_timeout_seconds: float = 60.0

    output_root: str = "./outputs"
    serve_artifacts: bool = True
    max_file_size_bytes: int = Field(default=50 * 1024 * 1024)


settings = Settings()
