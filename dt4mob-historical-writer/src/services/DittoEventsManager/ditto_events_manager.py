from src.database_engines.TimeScaleEngineManager import TimescaleDBEgineManager
from src.models.ditto_events import DittoEvent


class DittoEventsManager:
    def __init__(self,db_engine:TimescaleDBEgineManager):
        self.db_engine = db_engine

    def write(self,event: DittoEvent):
        with self.db_engine.get_session() as session:
            session.add(event)