import logging

from pydantic import Field
from typing import Literal
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)
from app.settings.auth import AuthSettings
from app.settings.timescale import TimeScaleSettings

LogLevel = Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]


class Settings(BaseSettings):
    log_level: LogLevel = Field(validation_alias="LOG_LEVEL", default="INFO")

    auth: AuthSettings
    timescale: TimeScaleSettings

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )


settings = Settings()  # ty:ignore[missing-argument]

logging.basicConfig(level=settings.log_level)
logging.debug(settings)
