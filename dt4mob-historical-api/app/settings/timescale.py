from pydantic import BaseModel


class TimeScaleSettings(BaseModel):
    database_timezone: str = "Europe/Lisbon"
    connection: str

    def get_connection(self):
        return self.connection.replace("postgresql", "postgresql+psycopg")
