from confluent_kafka import Consumer
from src.settings import settings
from src.services.DittoEventsManager.ditto_events_manager import DittoEventsManager
import json
import logging

from src.services.MessageProcessor.message_processor import parse_message

class KafkaConsumer:
    def __init__(self):
        self.consumer = Consumer(settings.kafka.as_dict())
        self.consumer.subscribe([settings.kafka.topic])
        logging.info(f"Subscribed to {settings.kafka.topic}")
    
    def consume(self,manager:DittoEventsManager):
        try:
            while True:
                msg = self.consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    logging.error(f"Error: {msg.error()}")
                    continue

                try:
                    msg_value = msg.value()
                    if msg_value is None:
                        continue
                    message_text = msg_value.decode('utf-8')
                    message_data = json.loads(message_text)
                    event = parse_message(message_data)
                    manager.write(event)
                    logging.debug("writed: %s", event)
                    self.consumer.commit(asynchronous=False)
                    
                except json.JSONDecodeError as e:
                    logging.error(f"JSON decode error: {e}")
                except Exception as e:
                    logging.error(f"Error processing message: {e}")


        except KeyboardInterrupt:
            logging.info("Shutting down consumer...")
        finally:
            self.consumer.close()