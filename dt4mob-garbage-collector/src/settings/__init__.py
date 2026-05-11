import logging

from typing import Literal
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)
from src.settings.ditto import DittoSettings
from src.settings.auth import AuthSettings


LogLevel = Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]


class Settings(BaseSettings):
    log_level: LogLevel = "INFO"

    ditto: DittoSettings = DittoSettings.model_construct()
    auth: AuthSettings = AuthSettings.model_construct()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_nested_delimiter="__",
    )


settings = Settings()

logging.basicConfig(level=settings.log_level)
logging.debug(settings)
