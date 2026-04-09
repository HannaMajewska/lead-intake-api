from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Lead Intake API"
    app_env: str = "dev"
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    enable_crm_sync: bool = False
    crm_provider: str = "mock"

    google_sheet_id: str = ""
    google_sheet_name: str = "Sheet1"
    google_credentials_path: str = "credentials/service_account.json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()