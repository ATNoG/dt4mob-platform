from app.models.util import Action
from datetime import datetime
from app.services.authentication_service import NginxAuthenticationService
from sqlalchemy.util.typing import Annotated
from fastapi.responses import JSONResponse
import http
from fastapi import APIRouter, Depends, status, Body
from sqlmodel import Session

from app.database_engine import get_session
from app.models.ditto_events import DittoEvent
from app.services.events_service import EventsService

def get_events_service(session: Session = Depends(get_session)):
    return EventsService(session)

auth: NginxAuthenticationService = NginxAuthenticationService()

router = APIRouter(tags=["events"], dependencies=[Depends(auth)])

@router.get("/things", response_model=list[str])
def read_available_things(thing_id_prefix: str | None = None, events_service: EventsService = Depends(get_events_service)):
    result = events_service.get_available_things(thing_id_prefix=thing_id_prefix)
    return result

@router.get("/events", response_model=list[DittoEvent])
def read_events(since: datetime, until: datetime | None = None, thing_id_prefix: str | None = None, action: Action | None = None, events_service: EventsService = Depends(get_events_service)):
    if until is None:
        until = datetime.now()
    result = events_service.get_events(since_iso_timestamp=since, until_iso_timestamp=until, thing_id_prefix=thing_id_prefix, action=action)
    return result

@router.get("/events/{thing_id}")
def read_events_by_thing(thing_id:str, since: datetime, until: datetime | None = None, events_service: EventsService = Depends(get_events_service)):
    if until is None:
        until = datetime.now()
    result = events_service.get_events_by_thing(thing_id=thing_id, since_iso_timestamp=since, until_iso_timestamp=until)
    return result

@router.post("/events")
def insert_events(events: Annotated[list[DittoEvent], Body(embed=True)], events_service: EventsService = Depends(get_events_service)):
    events_service.insert_events(events)
    return http.HTTPStatus.CREATED

@router.delete("/events/{thing_id}")
def delete_events(thing_id: str, since: datetime, until: datetime, events_service: EventsService = Depends(get_events_service)):

    values = events_service.delete_events(thing_id=thing_id, since_iso_timestamp=since, until_iso_timestamp=until)
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=values)