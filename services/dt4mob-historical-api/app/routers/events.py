from app.models.paths_response import PathResponseObject
from typing import Annotated
from datetime import datetime

from pydantic import BaseModel
from fastapi import APIRouter, Depends, status, Body, HTTPException
from fastapi_oidc import get_auth, IDToken
from sqlmodel import Session

from app.settings import settings
from app.models.util import Action
from app.database_engine import get_session
from app.models.ditto_events import DittoEvent
from app.services.events_service import EventsService


class ClientResourceAccess(BaseModel):
    roles: list[str] = []


class KeycloakToken(IDToken):
    resource_access: dict[str, ClientResourceAccess] = {}


auth = get_auth(
    client_id=settings.auth.client_id,
    audience=settings.auth.audience,
    base_authorization_server_uri=settings.auth.server_uri.rstrip("/"),
    issuer=settings.auth.issuer,  # ty:ignore[invalid-argument-type]: It's badly defined but it does allow mutliple issuers
    signature_cache_ttl=settings.auth.signature_cache_ttl,
    token_type=KeycloakToken,
)


def get_events_service(session: Annotated[Session, Depends(get_session)]):
    return EventsService(session)


def check_role(roles: list[str]):
    def check_role_inner(token: Annotated[KeycloakToken, Depends(auth)]):
        if settings.auth.client_id not in token.resource_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Missing role"
            )

        token_roles = token.resource_access[settings.auth.client_id].roles
        if not any(role in token_roles for role in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Missing role"
            )

    return check_role_inner


router = APIRouter(tags=["events"], dependencies=[Depends(auth)])


@router.get("/things", response_model=list[str])
def read_available_things(
    _check_role: Annotated[None, Depends(check_role(settings.auth.read_role))],
    events_service: Annotated[EventsService, Depends(get_events_service)],
    thing_id_prefix: str | None = None,
):
    result = events_service.get_available_things(thing_id_prefix=thing_id_prefix)
    return result

@router.get("/events/{thing_id}/paths", response_model=list[PathResponseObject])
def read_event_paths(
    _check_role: Annotated[None, Depends(check_role(settings.auth.read_role))],
    events_service: Annotated[EventsService, Depends(get_events_service)],
    thing_id: str,
    since: datetime,
    until: datetime | None = None,
):
    if until is None:
        until = datetime.now()
    result = events_service.get_event_paths_with_action(
        thing_id=thing_id, since_iso_timestamp=since, until_iso_timestamp=until
    )
    return result

@router.get("/events", response_model=list[DittoEvent])
def read_events(
    _check_role: Annotated[None, Depends(check_role(settings.auth.read_role))],
    events_service: Annotated[EventsService, Depends(get_events_service)],
    since: datetime,
    until: datetime | None = None,
    thing_id_prefix: str | None = None,
    path_prefix: str | None = None,
    action: Action | None = None,
):
    if until is None:
        until = datetime.now()
    result = events_service.get_events(
        since_iso_timestamp=since,
        until_iso_timestamp=until,
        thing_id_prefix=thing_id_prefix,
        path_prefix=path_prefix,
        action=action,
    )
    return result


@router.get("/events/{thing_id}")
def read_events_by_thing(
    _check_role: Annotated[None, Depends(check_role(settings.auth.read_role))],
    events_service: Annotated[EventsService, Depends(get_events_service)],
    thing_id: str,
    since: datetime,
    until: datetime | None = None,
    action: Action | None = None,
    path_prefix: str | None = None,
):
    if until is None:
        until = datetime.now()
    result = events_service.get_events_by_thing(
        thing_id=thing_id, since_iso_timestamp=since, until_iso_timestamp=until, path_prefix=path_prefix, action=action
    )
    return result


@router.post("/events", status_code=status.HTTP_201_CREATED)
def insert_events(
    _check_role: Annotated[None, Depends(check_role(settings.auth.write_role))],
    events_service: Annotated[EventsService, Depends(get_events_service)],
    events: Annotated[list[DittoEvent], Body(embed=True)],
):
    events_service.insert_events(events)
    return


@router.delete("/events/{thing_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_events(
    _check_role: Annotated[None, Depends(check_role(settings.auth.write_role))],
    events_service: Annotated[EventsService, Depends(get_events_service)],
    thing_id: str,
    since: datetime,
    until: datetime,
):

    events_service.delete_events(
        thing_id=thing_id, since_iso_timestamp=since, until_iso_timestamp=until
    )
    return
