from src.services.KafkaConsumer import KafkaConsumer
from src.services.DittoEventsManager import ditto_event_manager
import logging

def main():
    consumer = KafkaConsumer()

    logging.info("Staring consuming")
    consumer.consume(ditto_event_manager)


if __name__ == "__main__":
    main()
