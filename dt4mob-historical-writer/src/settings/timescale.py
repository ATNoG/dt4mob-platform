from pydantic import Field
from pydantic_settings import BaseSettings,SettingsConfigDict

class TimeScale(BaseSettings):
    database_timezone: str = Field(validation_alias="TIMESCALE_DATABASE_TIMEZONE",default="Europe/Lisbon")
    connection: str = Field(validation_alias="TIMESCALE_CONNECTION")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def get_connection(self):
        return self.connection.replace("postgresql","postgresql+psycopg")