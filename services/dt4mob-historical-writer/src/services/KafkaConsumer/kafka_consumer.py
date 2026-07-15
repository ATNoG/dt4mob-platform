from confluent_kafka import Consumer
from src.settings import settings
from src.services.DittoEventsManager.ditto_events_manager import DittoEventsManager
import json
import logging
import time

from src.services.MessageProcessor.message_processor import parse_message

class KafkaConsumer:
    def __init__(self):
        self.consumer = Consumer(settings.kafka.as_dict())
        self.consumer.subscribe([settings.kafka.topic])
        logging.info(f"Subscribed to {settings.kafka.topic}")
    
    def consume(self,manager:DittoEventsManager, batch_size:int=500, batch_timeout:int=5):
        batch = []
        last_flush_time = time.time()
        try:
            while True:
                msg = self.consumer.poll(1.0)
                
                if msg is not None:
                    if msg.error():
                        logging.error(f"Error: {msg.error()}")
                    else:
                        try:
                            msg_value = msg.value()
                            if msg_value is not None:
                                message_text = msg_value.decode('utf-8')
                                message_data = json.loads(message_text)
                                event = parse_message(message_data)
                                batch.append(event)
                        except json.JSONDecodeError as e:
                            logging.error(f"JSON decode error: {e}")
                        except Exception as e:
                            logging.error(f"Error processing message: {e}")

                # Check if it's time to flush the batch to the database
                current_time = time.time()
                reached_size_limit = len(batch) >= batch_size
                reached_time_limit = (current_time - last_flush_time) >= batch_timeout

                if batch and (reached_size_limit or reached_time_limit):
                    try:
                        logging.debug(f"Flushing batch of {len(batch)} messages to manager")
                        manager.write_batch(batch)
                    except Exception as e:
                        logging.error(f"Failed to write batch: {e}")
                    finally:
                        batch.clear()
                        last_flush_time = current_time


        except KeyboardInterrupt:
            logging.info("Shutting down consumer...")
        finally:
            self.consumer.close()