from src.services.ditto_api import DittoClient

from src.services.envelope_formatter.ditto_thing import envelop_formater
from src.models.ditto import DittoProtocolEnvelope

from datetime import datetime

class GarbageCollector:
    def __init__(self,client: DittoClient):
        self.client = client
    
    def get_expired_envelops(self) -> list[DittoProtocolEnvelope]:

        current_time = datetime.now()
        values = self.client.get_all_things_expired_lt(current_time)
        envelops = []
        for thing in values:
            envelops.append(envelop_formater.delete_message(thing))

        return envelops