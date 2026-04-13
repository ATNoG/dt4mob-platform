from typing import Generator
from sqlmodel import create_engine, SQLModel, Session
from contextlib import contextmanager

from src.settings import settings

class TimescaleDBEgineManager:
    def __init__(self):
        self.engine = create_engine(
            url=settings.timescale.get_connection(),
            echo= True if settings.log_level == "DEBUG" else False,
        )

    def create_db_tables(self):
        SQLModel.metadata.create_all(self.engine)

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        with Session(self.engine) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise