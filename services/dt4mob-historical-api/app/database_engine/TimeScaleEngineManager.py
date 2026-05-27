from sqlmodel import create_engine, SQLModel

from app.settings import settings

class TimescaleDBEgineManager:
    def __init__(self):
        self.engine = create_engine(
            url=settings.timescale.get_connection(),
            echo= True if settings.log_level == "DEBUG" else False,
        )

    def create_db_tables(self):
        SQLModel.metadata.create_all(self.engine)

    