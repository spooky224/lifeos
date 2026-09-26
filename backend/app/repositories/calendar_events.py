from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.calendar_event import (
    CalendarEvent,
    CalendarEventStatus,
)


class CalendarEventRepository:
    """
    Database access layer for CalendarEvent entities.
    """

    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        task_id: int | None,
        google_event_id: str,
        title: str,
        start_time: datetime,
        end_time: datetime,
        routine_id: int | None = None,
        recurrence_rule: str | None = None,
    ) -> CalendarEvent:

        if task_id is None and routine_id is None:
            raise ValueError(
                "CalendarEvent must belong to either a task or a routine."
            )

        if task_id is not None and routine_id is not None:
            raise ValueError(
                "CalendarEvent cannot belong to both a task and a routine."
            )

        calendar_event = CalendarEvent(
            task_id=task_id,
            routine_id=routine_id,
            google_event_id=google_event_id,
            title=title,
            start_time=start_time,
            end_time=end_time,
            recurrence_rule=recurrence_rule,
            status=CalendarEventStatus.SCHEDULED,
        )

        self.session.add(calendar_event)
        self.session.flush()

        return calendar_event

    def get_by_id(
        self,
        calendar_event_id: int,
    ) -> CalendarEvent | None:

        statement = select(CalendarEvent).where(
            CalendarEvent.id == calendar_event_id
        )

        return self.session.scalar(statement)

    def get_by_google_event_id(
        self,
        google_event_id: str,
    ) -> CalendarEvent | None:

        statement = select(CalendarEvent).where(
            CalendarEvent.google_event_id == google_event_id
        )

        return self.session.scalar(statement)

    def list_by_task(
        self,
        task_id: int,
    ) -> list[CalendarEvent]:

        statement = (
            select(CalendarEvent)
            .where(CalendarEvent.task_id == task_id)
            .order_by(CalendarEvent.start_time.asc())
        )

        return list(self.session.scalars(statement).all())

    def list_by_routine(
        self,
        routine_id: int,
    ) -> list[CalendarEvent]:

        statement = (
            select(CalendarEvent)
            .where(CalendarEvent.routine_id == routine_id)
            .order_by(CalendarEvent.start_time.asc())
        )

        return list(self.session.scalars(statement).all())

    def list_between(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> list[CalendarEvent]:

        statement = (
            select(CalendarEvent)
            .where(
                CalendarEvent.start_time < end_time,
                CalendarEvent.end_time > start_time,
            )
            .order_by(CalendarEvent.start_time.asc())
        )

        return list(self.session.scalars(statement).all())

    def update_status(
        self,
        calendar_event: CalendarEvent,
        status: CalendarEventStatus,
    ) -> CalendarEvent:

        calendar_event.status = status
        self.session.flush()

        return calendar_event

    def delete(
        self,
        calendar_event: CalendarEvent,
    ) -> None:

        self.session.delete(calendar_event)
        self.session.flush()
        
    def list_all(self):
        statement = select(CalendarEvent).order_by(CalendarEvent.start_time.asc())
        return list(self.session.scalars(statement).all())