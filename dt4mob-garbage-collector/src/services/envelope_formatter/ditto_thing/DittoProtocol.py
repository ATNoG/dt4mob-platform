import uuid
from src.models.ditto import (
    DittoProtocolEnvelope,
    Headers
)


class DittoThingEnvelopeFormatter():

    def __init__(self) -> None:
        pass

    def delete_message(self, delete_thing_id: str) -> DittoProtocolEnvelope:
        correlation_id = str(uuid.uuid4())
        return DittoProtocolEnvelope(
                topic=f"{delete_thing_id.replace(":","/")}/things/twin/commands/delete",
                headers=Headers(correlation_id=correlation_id),
                path="/",
            )
