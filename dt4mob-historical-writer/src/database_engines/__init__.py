from src.database_engines.TimeScaleEngineManager import TimescaleDBEgineManager
from src.models.ditto_events import DittoEvent

timescale_engine = TimescaleDBEgineManager()
timescale_engine.create_db_tables()