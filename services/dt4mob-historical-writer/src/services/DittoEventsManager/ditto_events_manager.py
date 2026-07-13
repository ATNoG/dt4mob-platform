import logging
from src.database_engines.TimeScaleEngineManager import TimescaleDBEgineManager
from src.models.ditto_events import DittoEvent


class DittoEventsManager:
    def __init__(self,db_engine:TimescaleDBEgineManager):
        self.db_engine = db_engine

    def write(self,event: DittoEvent):
        with self.db_engine.get_session() as session:
            session.add(event)
    
    def write_batch(self, events: list[DittoEvent]):
        """
        Writes a list of events to the database using a single session and transaction.
        """
        with self.db_engine.get_session() as session:
            try:
                session.add_all(events)
                session.commit()
                logging.info(f"Successfully wrote {len(events)} events to the database.")
            except Exception as e:
                session.rollback()
                logging.error(f"Database transaction rolled back due to error: {e}")
                raise e