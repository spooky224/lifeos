from typing import Any

from app.services.google_calendar import create_event


def create_calendar_event(
    title: str,
    start: str,
    end: str,
    recurrence: list[str] | None = None,
) -> dict[str, Any]:

    created_event = create_event(
        title=title,
        start=start,
        end=end,
        recurrence=recurrence,
    )

    return {
        "status": "success",
        "action": "create_calendar_event",
        "title": title,
        "start": start,
        "end": end,
        "recurrence": recurrence,
        "event_id": created_event["id"],
        "calendar_link": created_event.get("htmlLink"),
        "message": "Calendar event created successfully.",
    }