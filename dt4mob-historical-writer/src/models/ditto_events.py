from typing import Optional
from datetime import datetime
from enum import Enum

from pydantic import PositiveInt
from sqlalchemy import event, text, Integer, Identity
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, SQLModel
from sqlmodel import Enum as SAEnum


class Action(str, Enum):
    MODIFIED = "modified"
    CREATE = "created"
    DELETE = "deleted"
    MERGED = "merged"


class DittoEvent(SQLModel, table=True):
    time: datetime = Field(primary_key=True)
    index: Optional[int] = Field(
        sa_column=Column(Integer, Identity(start=1), primary_key=True)
    )
    thing_id: str = Field(index=True)
    action: Action = Field(
        sa_column=Column(SAEnum(Action, name="action_enum"), nullable=False)
    )
    revision: PositiveInt | None = Field(nullable=True)
    path: str = Field(nullable=False)

    value: dict = Field(default=None, sa_type=JSONB)

    __timescale_config__ = {
        "time_column": "time",
        "chunk_time_interval": "1 days",
        "compress": True,
        "compress_segmentby": "thing_id",
        "compress_orderby": "time DESC",
        "compress_interval": "7 days",
    }

@event.listens_for(DittoEvent.__table__, "after_create")  # ty:ignore[unresolved-attribute]
def create_timescale_features(target, connection, **kw):
    config = DittoEvent.__timescale_config__

    connection.execute(
        text(
            f"SELECT create_hypertable('{target.name}', '{config['time_column']}', "
            f"chunk_time_interval => INTERVAL '{config['chunk_time_interval']}', "
            f"if_not_exists => TRUE);"
        )
    )

    if config.get("compress"):
        connection.execute(
            text(
                f"ALTER TABLE {target.name} SET (timescaledb.compress, "
                f"timescaledb.compress_segmentby = '{config['compress_segmentby']}', "
                f"timescaledb.compress_orderby = '{config['compress_orderby']}');"
            )
        )
        connection.execute(
            text(
                f"SELECT add_compression_policy('{target.name}', INTERVAL '{config['compress_interval']}', if_not_exists => TRUE);"
            )
        )
