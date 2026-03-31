from src.services.ditto_api import ditto_client

from .garbage_collector import GarbageCollector

garbage_collector = GarbageCollector(client=ditto_client)
