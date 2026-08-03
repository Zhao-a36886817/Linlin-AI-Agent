from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    linlin_env: str = "development"
    linlin_app_name: str = "Linlin Agent"
    linlin_app_version: str = "0.1.0"

    linlin_backend_host: str = "127.0.0.1"
    linlin_backend_port: int = 8000
    linlin_frontend_origin: str = "http://localhost:1420"

    max_parallel_agents: int = 4

    workspace_root: Path = PROJECT_ROOT / "workspace"
    output_root: Path = PROJECT_ROOT / "outputs"
    log_root: Path = PROJECT_ROOT / "logs"
    data_root: Path = PROJECT_ROOT / "data"


@lru_cache
def get_settings() -> Settings:
    return Settings()
