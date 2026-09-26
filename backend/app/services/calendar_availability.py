from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo


LIFEOS_TIMEZONE = ZoneInfo("Africa/Tunis")


def calculate_available_slots(
    events: list[dict[str, Any]],
    start_date: datetime,
    end_date: datetime,
    workday_start: int = 9,
    workday_end: int = 18,
    minimum_duration_minutes: int = 30,
) -> list[dict[str, str]]:
    """
    Calculate free calendar slots from real Google Calendar events.

    All datetime values are normalized to the LIFEOS timezone.
    """

    start_date = _ensure_timezone(start_date)
    end_date = _ensure_timezone(end_date)

    available_slots = []

    current_date = start_date.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    final_date = end_date.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    while current_date <= final_date:

        day_start = current_date.replace(
            hour=workday_start
        )

        day_end = current_date.replace(
            hour=workday_end
        )

        # Never return time that is already in the past.
        if current_date.date() == start_date.date():
            day_start = max(day_start, start_date)

        day_events = []

        for event in events:
            start_data = event.get("start", {})
            end_data = event.get("end", {})

            event_start_str = start_data.get("dateTime")
            event_end_str = end_data.get("dateTime")

            if not event_start_str or not event_end_str:
                continue

            event_start = _ensure_timezone(
                datetime.fromisoformat(event_start_str)
            )

            event_end = _ensure_timezone(
                datetime.fromisoformat(event_end_str)
            )

            # Ignore events outside this working day.
            if event_end <= day_start or event_start >= day_end:
                continue

            # Restrict events to working hours.
            event_start = max(event_start, day_start)
            event_end = min(event_end, day_end)

            day_events.append(
                (event_start, event_end)
            )

        # Sort events chronologically.
        day_events.sort(key=lambda event: event[0])

        cursor = day_start

        for event_start, event_end in day_events:

            if event_start > cursor:

                duration = (
                    event_start - cursor
                ).total_seconds() / 60

                if duration >= minimum_duration_minutes:
                    available_slots.append(
                        {
                            "start": cursor.isoformat(),
                            "end": event_start.isoformat(),
                        }
                    )

            if event_end > cursor:
                cursor = event_end

        # Check remaining time after the last event.
        if cursor < day_end:

            duration = (
                day_end - cursor
            ).total_seconds() / 60

            if duration >= minimum_duration_minutes:
                available_slots.append(
                    {
                        "start": cursor.isoformat(),
                        "end": day_end.isoformat(),
                    }
                )

        current_date += timedelta(days=1)

    return available_slots


def _ensure_timezone(value: datetime) -> datetime:
    """
    Ensure a datetime is timezone-aware and normalized
    to the LIFEOS timezone.
    """

    if value.tzinfo is None:
        return value.replace(tzinfo=LIFEOS_TIMEZONE)

    return value.astimezone(LIFEOS_TIMEZONE)


def generate_candidate_slots(
    available_slots: list[dict[str, str]],
    duration_minutes: int,
) -> list[dict[str, str]]:
    """
    Generate valid calendar candidates from free periods.

    Each candidate has exactly the requested duration.
    """

    candidates = []

    for slot in available_slots:
        start = datetime.fromisoformat(slot["start"])
        end = datetime.fromisoformat(slot["end"])

        duration = (
            end - start
        ).total_seconds() / 60

        if duration >= duration_minutes:
            candidate_end = start + timedelta(
                minutes=duration_minutes
            )

            candidates.append(
                {
                    "start": start.isoformat(),
                    "end": candidate_end.isoformat(),
                }
            )

    return candidates