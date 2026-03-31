from src.models.ditto_events import DittoEvent,Action


def parse_message(msg):
    topic_processed = msg["topic"].split("/")

    dittomsg = DittoEvent(
        time=msg["timestamp"],
        thing_id=f"{topic_processed[0]}:{topic_processed[1]}",
        action=Action(topic_processed[5]),
        path=msg["path"],
        revision=msg["revision"],
        value=msg.get("value", {})
    )

    return dittomsg
