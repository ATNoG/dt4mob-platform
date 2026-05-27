from typing import Generator

from sqlmodel import Session
from app.database_engine.TimeScaleEngineManager import TimescaleDBEgineManager

# important to import the models here to create the tables in the database
from app.models.ditto_events import DittoEvent

timescale_engine = TimescaleDBEgineManager()
timescale_engine.create_db_tables()


def get_session() -> Generator[Session, None, None]:
    with Session(timescale_engine.engine) as session:
        try:
            yield session
        except Exception:
            # Optional: rollback if an unhandled error occurs
            session.rollback()
            raise
        finally:
            session.close()