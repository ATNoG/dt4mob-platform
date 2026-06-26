from src.models.ditto_events import DittoEvent,Action


def parse_message(msg) -> DittoEvent:
    topic_processed = msg["topic"].split("/")

    headers = msg.get("headers", {})
    override_timestamp = headers.get("dt4mob-historic-timestamp-override")
    event_time = override_timestamp if override_timestamp else msg["timestamp"]

    dittomsg = DittoEvent(
        time=event_time,
        thing_id=f"{topic_processed[0]}:{topic_processed[1]}",
        action=Action(topic_processed[5]),
        path=msg["path"],
        revision=msg["revision"],
        value=msg.get("value", {})
    )

    return dittomsg
