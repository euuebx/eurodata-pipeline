"""Application settings loaded from environment variables."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./eurodata.db"
    ecb_start_date: str = "2020-01-01"
    ecb_timeout_seconds: int = 30
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
