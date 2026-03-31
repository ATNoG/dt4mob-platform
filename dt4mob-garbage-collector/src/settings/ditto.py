from pydantic import Field

from pydantic_settings import BaseSettings, SettingsConfigDict


class DittoSettings(BaseSettings):
    api_url: str = Field(
        default="localhost:8080", 
        validation_alias="ditto_api_url"
    )
    base_api_path: str = Field(
        default="/api/2", 
        validation_alias="ditto_base_api_path"
    )
    base_ws_path: str = Field(
        default="/ws/2",
        validation_alias="ditto_base_ws_path"
    )
    
    username: str = Field(
        default=None, 
        validation_alias="ditto_username"
    )
    password: str|None = Field(
        default=None,
        validation_alias="ditto_password"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def get_auth(self) -> str:
        return f"{self.username}:{self.password}"
    
    def get_base_url(self) -> str:
        base_url = "http://" + self.api_url
        stripped_url = str(base_url).rstrip("/")
        stripped_base_path = self.base_api_path.strip("/")
        return f"{stripped_url}/{stripped_base_path}"

    def get_base_ws(self) -> str:
        base_url = "ws://" + self.api_url
        stripped_url = str(base_url).rstrip("/")
        stripped_base_path = self.base_ws_path.strip("/")
        return f"{stripped_url}/{stripped_base_path}"