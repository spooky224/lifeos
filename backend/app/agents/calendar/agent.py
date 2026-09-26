import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.db.session import SessionLocal
from app.repositories.calendar_events import CalendarEventRepository
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from app.graph.state import LifeOSState
from app.tools.calendar.get_events import get_calendar_events
from app.tools.calendar.find_available_slots import find_available_slots


load_dotenv()

LIFEOS_TIMEZONE = ZoneInfo("Africa/Tunis")


class CalendarProposal(BaseModel):
    proposed_start: str = Field(
        description="Proposed start date and time in ISO format."
    )

    proposed_end: str = Field(
        description="Proposed end date and time in ISO format."
    )

    title: str = Field(
        description="Calendar event title."
    )

    explanation: str = Field(
        description="Why this time slot is appropriate."
    )


model = ChatGroq(
    model=os.getenv("LIFEOS_MODEL"),
    temperature=0,
)

calendar_model = model.with_structured_output(
    CalendarProposal,
    method="json_mode",
)


def calendar_agent(state: LifeOSState) -> LifeOSState:
    task = state["task_context"]

    pending_reschedule = state.get("pending_reschedule")

    if pending_reschedule:
        task_id = pending_reschedule["task_id"]
    else:
        task_id = task["task_id"]
    
    google_event_id = None

    if pending_reschedule:
        session = SessionLocal()

        try:
            calendar_event_repository = CalendarEventRepository(session)

            calendar_event = calendar_event_repository.get_by_id(
                pending_reschedule["calendar_event_id"]
            )

            if calendar_event is None:
                raise ValueError(
                    f"Calendar event #{pending_reschedule['calendar_event_id']} not found."
                )

            google_event_id = calendar_event.google_event_id

        finally:
            session.close()

    now = datetime.now(LIFEOS_TIMEZONE)

    # Temporary scheduling window:
    # current week.
    #
    # Later this will come directly from the
    # user's interpreted scheduling intention.
    week_start = (
        now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        - timedelta(days=now.weekday())
    )

    start_of_week = max(
        week_start,
        now,
    )

    end_of_week = week_start + timedelta(days=7)
    # Get REAL events only inside the scheduling window.
    events = get_calendar_events(
        start_datetime=start_of_week,
        end_datetime=end_of_week,
    )

    # Calculate REAL available slots.
    available_slots = find_available_slots(
        events=events,
        start_datetime=start_of_week,
        end_datetime=end_of_week,
    )

    calendar_context = {
        "timezone": "Africa/Tunis",
        "available_slots": available_slots,
    }

    prompt = f"""
You are the Calendar Agent of LIFEOS.

Task:
{task}

Available calendar slots:
{available_slots}

Select exactly ONE slot that is long enough
for the requested duration.

IMPORTANT:
- Select a slot from the provided list.
- Do not invent a date.
- Do not overlap existing events.
- Do not use a busy period.
- Respect the requested duration.
- Return the selected time exactly.
- Give a brief explanation.
- Return ONLY valid JSON.
- Do not return Markdown.
- Do not write any text before or after the JSON.

Return exactly this structure:

{{
  "proposed_start": "YYYY-MM-DDTHH:MM:SS+01:00",
  "proposed_end": "YYYY-MM-DDTHH:MM:SS+01:00",
  "title": "calendar event title",
  "explanation": "brief explanation"
}}
"""

    result = calendar_model.invoke(prompt)

    return {
        "calendar_context": calendar_context,
        "proposed_actions": [
            {
                "type": (
                    "reschedule_calendar_event"
                    if pending_reschedule
                    else "create_calendar_event"
                ),
                "task_id": task_id,
                "calendar_event_id": (
                    pending_reschedule["calendar_event_id"]
                    if pending_reschedule
                    else None
                ),
                "google_event_id": google_event_id,
                "title": result.title,
                "start": result.proposed_start,
                "end": result.proposed_end,
                "explanation": result.explanation,
            }
        ],
        "messages": state.get("messages", []) + [
            {
                "role": "calendar_agent",
                "content": result.explanation,
            }
        ],
    }