from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.repositories.calendar_events import CalendarEventRepository
from app.services.google_calendar import delete_event


class CalendarService:
    def __init__(self, session: Session):
        self.session = session
        self.calendar_event_repository = CalendarEventRepository(session)

    def remove_event(self, calendar_event_id: int):
        calendar_event = self.calendar_event_repository.get_by_id(calendar_event_id)

        if calendar_event is None:
            raise ValueError(
                f"Calendar event #{calendar_event_id} not found."
            )

        try:
            delete_event(event_id=calendar_event.google_event_id)
        except HttpError as e:
            if e.resp.status not in {404, 410}:
                raise

        self.calendar_event_repository.delete(calendar_event)
        self.session.flush()

        return calendar_event