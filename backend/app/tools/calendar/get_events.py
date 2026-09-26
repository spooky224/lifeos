from datetime import datetime
from typing import Any

from app.services.google_calendar import get_events


def get_calendar_events(
    start_datetime: datetime,
    end_datetime: datetime,
    calendar_id: str = "primary",
) -> list[dict[str, Any]]:
    """
    Retrieve calendar events inside a specific time window.
    """

    return get_events(
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        calendar_id=calendar_id,
    )