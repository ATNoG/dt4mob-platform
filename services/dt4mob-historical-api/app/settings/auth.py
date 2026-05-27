from pydantic import BaseModel, PositiveInt


class AuthSettings(BaseModel):
    client_id: str
    audience: str = "account"
    server_uri: str
    issuer: str | list[str]
    signature_cache_ttl: PositiveInt = 3600

    read_role: str = "historical-read"
    write_role: str = "historical-write"
