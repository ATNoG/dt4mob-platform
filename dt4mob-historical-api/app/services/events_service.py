from app.models.util import Action
from datetime import datetime
from sqlmodel import Session, col
from sqlmodel import select


from app.models.ditto_events import DittoEvent

class EventsService():
    def __init__(self, session: Session):
        self.session = session
    
    def get_available_things(self,thing_id_prefix: str | None = None) -> list[str]:
        query = select(DittoEvent.thing_id).distinct()
        if thing_id_prefix:
            query = query.where(DittoEvent.thing_id.startswith(thing_id_prefix))
        result = self.session.execute(query)

        return [row[0] for row in result.all()]

    def get_events(self,since_iso_timestamp: datetime, until_iso_timestamp: datetime = datetime.now(), thing_id_prefix: str | None = None, action: Action| None = None,limit:int|None = None, ) -> list[DittoEvent]:
        query = select(DittoEvent).where(
                                            (col(DittoEvent.time) >= since_iso_timestamp) & 
                                            (col(DittoEvent.time) <= until_iso_timestamp)
                                            )
                                            
        if thing_id_prefix is not None:
            query = query.where(DittoEvent.thing_id.startswith(thing_id_prefix))
        if action is not None:
            query = query.where(col(DittoEvent.action) == action)


        query = query.order_by(col(DittoEvent.time).desc())
        result = self.session.exec(query)
            
        return list(result)
    
    def get_events_by_thing(self,thing_id: str,since_iso_timestamp: datetime,until_iso_timestamp: datetime = datetime.now()) -> list[DittoEvent]:
        query = select(DittoEvent).where(
            (DittoEvent.thing_id == thing_id) &
            (DittoEvent.time >= since_iso_timestamp) &
            (DittoEvent.time <= until_iso_timestamp)
        ).order_by(col(DittoEvent.time).desc())
        result = self.session.exec(query).all()
        return list(result)

    def insert_events(self, events: list[DittoEvent]) -> None:
        for event in events:
            self.session.add(event)
        self.session.commit()
    
    def delete_events(self, thing_id: str, since_iso_timestamp: datetime, until_iso_timestamp: datetime) -> list[DittoEvent]:
        query = select(DittoEvent).where(
            (col(DittoEvent.thing_id) == thing_id) &
            (col(DittoEvent.time) >= since_iso_timestamp) &
            (col(DittoEvent.time) <= until_iso_timestamp)
        )
        events_to_delete = self.session.exec(query).all()
        for event in events_to_delete:
            self.session.delete(event)
        self.session.commit()

        return list(events_to_delete)