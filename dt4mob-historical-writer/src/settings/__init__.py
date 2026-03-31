import logging

from pydantic import Field
from typing import Literal
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)
from src.settings.kafka import KafkaSettings
from src.settings.timescale import TimeScale

LogLevel = Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]

class Settings(BaseSettings):
    log_level: LogLevel = Field(validation_alias="LOG_LEVEL",default="INFO")

    kafka: KafkaSettings = KafkaSettings()
    timescale: TimeScale = TimeScale()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        extra="ignore"
    )



settings = Settings()

logging.basicConfig(level=settings.log_level)
logging.debug(settings)