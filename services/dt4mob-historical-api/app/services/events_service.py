from sqlalchemy import or_
from typing import Any, Literal
from app.models.util import Action
from datetime import datetime, timezone
from sqlmodel import Session, col, text, Float
from sqlmodel import select,delete, func
from sqlalchemy.dialects.postgresql import JSONPATH
from sqlalchemy.exc import DataError, ProgrammingError
from fastapi import HTTPException, status


from app.models.ditto_events import DittoEvent
from app.models.paths_response import PathResponseObject


class EventsService:
    def __init__(self, session: Session):
        self.session = session

    def get_available_things(self, thing_id_prefix: str | None = None) -> list[str]:
        query = select(DittoEvent.thing_id).distinct()
        if thing_id_prefix:
            query = query.where(DittoEvent.thing_id.startswith(thing_id_prefix))
        result = self.session.exec(query)

        return list(result.all())

    def get_event_paths_with_action(self, thing_id: str, since_iso_timestamp: datetime, until_iso_timestamp: datetime) -> list[PathResponseObject]:
        query = (
            select(DittoEvent.path, DittoEvent.action)
            .where(
                (col(DittoEvent.thing_id) == thing_id)
                & (col(DittoEvent.time) >= since_iso_timestamp)
                & (col(DittoEvent.time) <= until_iso_timestamp)
            )
            .distinct()
        )
        result = self.session.exec(query)
        return [PathResponseObject(path=path, action=action) for path, action in result.all()]  # ty:ignore[invalid-argument-type]

    def get_events(
        self,
        since_iso_timestamp: datetime,
        until_iso_timestamp: datetime = datetime.now(timezone.utc),
        thing_id_prefix: str | None = None,
        path_prefix: str | None = None,
        action: Action | None = None,
        limit: int | None = None,
    ) -> list[DittoEvent]:
        query = select(DittoEvent).where(
            (col(DittoEvent.time) >= since_iso_timestamp)
            & (col(DittoEvent.time) <= until_iso_timestamp)
        )

        if thing_id_prefix is not None:
            query = query.where(DittoEvent.thing_id.startswith(thing_id_prefix))
        if action is not None:
            query = query.where(col(DittoEvent.action) == action)
        if path_prefix is not None:
            query = query.where(DittoEvent.path.startswith(path_prefix))

        query = query.order_by(col(DittoEvent.time).desc())
        result = self.session.exec(query)

        return list(result)

    def get_events_by_thing(
        self,
        thing_id: str,
        since_iso_timestamp: datetime,
        until_iso_timestamp: datetime = datetime.now(timezone.utc),
        path_prefix: str | None = None,
        action: Action | None = None,
    ) -> list[DittoEvent]:
        query = (
            select(DittoEvent)
            .where(
                (DittoEvent.thing_id == thing_id)
                & (DittoEvent.time >= since_iso_timestamp)
                & (DittoEvent.time <= until_iso_timestamp)
            )
            .order_by(col(DittoEvent.time).desc())
        )
        if path_prefix is not None:
            query = query.where(DittoEvent.path.startswith(path_prefix))
        if action is not None:
            query = query.where(col(DittoEvent.action) == action)
        result = self.session.exec(query).all()
        return list(result)

    def insert_events(self, events: list[DittoEvent]) -> None:
        for event in events:
            self.session.add(event)
        self.session.commit()

    def delete_events(
        self,
        thing_id: str,
        since_iso_timestamp: datetime,
        until_iso_timestamp: datetime,
    ) -> int:
        query = delete(DittoEvent).where(
            (col(DittoEvent.thing_id) == thing_id)
            & (col(DittoEvent.time) >= since_iso_timestamp)
            & (col(DittoEvent.time) <= until_iso_timestamp)
        )
        result = self.session.exec(query)
        self.session.commit()

        return result.rowcount

    def get_jsonpath_projection(
        self,
        json_path: str,
        thing_id: str,
        since_iso_timestamp: datetime,
        path_prefix: str | None = None,
        until_iso_timestamp: datetime = datetime.now(timezone.utc),
    ) -> list[Any]:

        typed_json_path = func.cast(json_path, JSONPATH)
        extracted_field = func.jsonb_path_query(DittoEvent.value, typed_json_path)

        query = select(extracted_field).where(
                (col(DittoEvent.time) >= since_iso_timestamp)
                & (col(DittoEvent.time) <= until_iso_timestamp)
            )
            
        if thing_id:
            query = query.where(col(DittoEvent.thing_id) == thing_id)
        if path_prefix:
            query = query.where(DittoEvent.path.startswith(path_prefix))
            
        result = self.session.exec(query)
        return list(result.all())

    def get_events_custom_time_buckets(
        self,
        json_path: str,
        since_iso_timestamp: datetime,
        until_iso_timestamp: datetime,
        bucket_minutes: int | None = None,
        agg_type: Literal["count", "sum", "avg", "min", "max"] = "count",
        thing_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Groups events into custom time buckets of arbitrary width (in seconds).
        If bucket_seconds is None or 0, returns a single "all time" bucket.
        """
        typed_json_path = func.cast(json_path, JSONPATH)
        extracted_value = func.jsonb_path_query_first(DittoEvent.value, typed_json_path)
        
        agg_functions = {
            "count": func.count,
            "sum": func.sum,
            "avg": func.avg,
            "min": func.min,
            "max": func.max
        }
        chosen_agg = agg_functions[agg_type]
        
        if agg_type in ["sum", "avg", "min", "max"]:
            extracted_value = func.cast(extracted_value, Float)

        is_all_time = (bucket_minutes is None or bucket_minutes <= 0)
        if is_all_time:
            time_bucket = func.min(col(DittoEvent.time)).label("bucket")
        else:
            time_bucket = func.time_bucket_gapfill(
                text(f"'{bucket_minutes} minutes'"),
                col(DittoEvent.time),
                since_iso_timestamp,
                until_iso_timestamp
            ).label("bucket")

        query = select(time_bucket, chosen_agg(extracted_value).label("value")).where(
            (col(DittoEvent.time) >= since_iso_timestamp)
            & (col(DittoEvent.time) <= until_iso_timestamp)
        )

        if thing_id:
            query = query.where(col(DittoEvent.thing_id) == thing_id)

        if not is_all_time:
            query = query.group_by(text("bucket")).order_by(text("bucket ASC"))

        try:
            result = self.session.exec(query).all()
        except DataError as e:
            self.session.rollback()
            
            if "cannot cast jsonb object to type double precision" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Aggregation type '{agg_type}' requires a numeric value. "
                        f"The provided JSONPath '{json_path}' resolved to an object or dictionary instead. "
                        f"Please update your path to target a numeric field, or switch your agg_type to 'count'."
                    )
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Data processing error: {str(e.orig)}"
            )
        except ProgrammingError as e:
            self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSONPath expression syntax: '{json_path}'. Details: {str(e.orig)}"
            )
        
        if is_all_time:
            val = result[0][1] if result else None
            return [{"bucket": since_iso_timestamp.isoformat(), "value": val}]
            
        return [
            {"bucket": row.bucket.isoformat(), "value": row.value}  # ty:ignore[unresolved-attribute]
            for row in result
        ]


    def get_events_custom_time_buckets_with_path(
            self,
            json_path: str,
            since_iso_timestamp: datetime,
            until_iso_timestamp: datetime,
            path_prefixes: str,
            bucket_minutes: int | None = None,
            agg_type: Literal["count", "sum", "avg", "min", "max"] = "count",
            thing_id: str | None = None,
        ) -> list[dict[str, Any]]:
            """
            Groups events into custom time buckets, segmented by multiple path prefixes.
            """
            if path_prefixes:
                path_prefixes_arr = path_prefixes.split(",")

            typed_json_path = func.cast(json_path, JSONPATH)
            extracted_value = func.jsonb_path_query_first(DittoEvent.value, typed_json_path)
            
            agg_functions = {
                "count": func.count,
                "sum": func.sum,
                "avg": func.avg,
                "min": func.min,
                "max": func.max
            }
            chosen_agg = agg_functions[agg_type]
            
            if agg_type in ["sum", "avg", "min", "max"]:
                extracted_value = func.cast(extracted_value, Float)

            is_all_time = (bucket_minutes is None or bucket_minutes <= 0)
            if is_all_time:
                time_bucket = func.min(col(DittoEvent.time)).label("bucket")
            else:
                time_bucket = func.time_bucket_gapfill(
                    text(f"'{bucket_minutes} minutes'"),
                    col(DittoEvent.time),
                    since_iso_timestamp,
                    until_iso_timestamp
                ).label("bucket")

            query = select(
                col(DittoEvent.path).label("path"), 
                time_bucket, 
                chosen_agg(extracted_value).label("value")
            ).where(
                (col(DittoEvent.time) >= since_iso_timestamp)
                & (col(DittoEvent.time) <= until_iso_timestamp)
            )

            if thing_id:
                query = query.where(col(DittoEvent.thing_id) == thing_id)
                
            prefix_conditions = [col(DittoEvent.path).startswith(p) for p in path_prefixes_arr]
            query = query.where(or_(*prefix_conditions))

            if not is_all_time:
                query = query.group_by(DittoEvent.path, text("bucket")).order_by(text("bucket ASC"))
            else:
                query = query.group_by(DittoEvent.path)

            try:
                result = self.session.exec(query).all()
            except DataError as e:
                self.session.rollback()
                raise
            except ProgrammingError as e:
                self.session.rollback()
                raise
            
            if is_all_time:
                return [
                    {
                        "path": row.path, 
                        "bucket": since_iso_timestamp.isoformat(), 
                        "value": row.value
                    }
                    for row in result
                ]
                
            return [
                {
                    "path": row.path,
                    "bucket": row.bucket.isoformat(), 
                    "value": row.value
                }
                for row in result
            ]