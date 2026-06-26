from src.models.ditto_events import DittoEvent,Action
import logging
from datetime import datetime

def parse_message(msg) -> DittoEvent:
    topic_processed = msg["topic"].split("/")
    headers = msg.get("headers", {})

    override_timestamp = headers.get("dt4mob-historic-timestamp-override")
    event_time = None

    if override_timestamp and isinstance(override_timestamp, str):
        try:
            dt = datetime.fromisoformat(override_timestamp.replace("Z", "+00:00"))
            event_time = dt.isoformat()
        except ValueError:
            logging.warning(
                f"Malformed historic override timestamp detected: '{override_timestamp}'. "
                "Falling back to message default timestamp."
            )
    if not event_time:
        event_time = msg["timestamp"]

    dittomsg = DittoEvent(
        time=event_time,
        thing_id=f"{topic_processed[0]}:{topic_processed[1]}",
        action=Action(topic_processed[5]),
        path=msg["path"],
        revision=msg["revision"],
        value=msg.get("value", {})
    )

    return dittomsg
