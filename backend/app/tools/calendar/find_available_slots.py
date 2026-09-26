from datetime import datetime
from typing import Any

from app.services.calendar_availability import calculate_available_slots


def find_available_slots(
    events: list[dict[str, Any]],
    start_datetime: datetime,
    end_datetime: datetime,
    minimum_duration_minutes: int = 30,
) -> list[dict[str, str]]:
    """
    Find free calendar periods inside a scheduling window.
    """

    return calculate_available_slots(
        events=events,
        start_date=start_datetime,
        end_date=end_datetime,
        minimum_duration_minutes=minimum_duration_minutes,
    )