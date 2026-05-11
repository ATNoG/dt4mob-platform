import httpx
from .ditto_api import DittoClient

from src.settings import settings
from src.services.auth import auth_service


def _new_instance():
    http_client = httpx.AsyncClient()
    return DittoClient(
        client=http_client, auth_service=auth_service, ditto_settings=settings.ditto
    )


ditto_client = _new_instance()
