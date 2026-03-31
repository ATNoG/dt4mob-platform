from datetime import datetime
from typing import Annotated, Any, Dict, Iterable, List, Optional

from pydantic import BaseModel, ConfigDict, Field

RequestedAck = Annotated[str, Field(pattern=r"[a-zA-Z0-9-_:]{3,100}")]

class SearchResponse(BaseModel):
    items: Optional[list[Any]] = None
    cursor: Optional[str] = None

class Headers(BaseModel):
    model_config = ConfigDict(validate_by_name=True)

    content_type: Annotated[Optional[str], Field(alias="content-type")] = None
    correlation_id: Annotated[str, Field(alias="correlation-id")]
    ditto_originator: Annotated[Optional[str], Field(alias="ditto-originator")] = None
    If_Match: Annotated[Optional[str], Field(alias="If-Match")] = None
    If_None_Match: Annotated[Optional[str], Field(alias="If-None-Match")] = None
    if_equal: Annotated[Optional[str], Field(alias="if-equal")] = None
    response_required: Annotated[Optional[bool], Field(alias="response-required")] = (
        True
    )
    requested_acks: Annotated[
        Optional[List[RequestedAck]], Field(alias="requested-acks")
    ] = None
    timeout: Annotated[Optional[str], Field()] = None
    version: Annotated[Optional[int], Field(ge=1, le=2)] = None
    condition: Annotated[Optional[str], Field()] = None


class DittoProtocolEnvelope(BaseModel):
    topic: str
    headers: Headers
    path: str
    fields: Optional[str] = None
    value: Optional[Dict[str, Any]] = None
    extra: Optional[Dict[str, Any]] = None

    revision: Optional[float] = None
    timestamp: Optional[datetime] = None


class StateProperties(BaseModel):
    properties: Dict[str, Any] = {}


class TimestampProperties(BaseModel):
    value: Optional[datetime] = None


class Timestamp(BaseModel):
    properties: TimestampProperties = TimestampProperties()


class State(BaseModel):
    properties: Dict[str, Any] = {}


class VehicleFeatures(BaseModel):
    state: State = State()


class VehicleAttributes(BaseModel):
    length: float


class BaseEmptyVehicle(BaseModel):
    policyId: str
    attributes: VehicleAttributes
    features: VehicleFeatures = VehicleFeatures()

def getTimeStampClass(timestamp: datetime) -> Timestamp:
    return Timestamp(properties=TimestampProperties(value=timestamp))