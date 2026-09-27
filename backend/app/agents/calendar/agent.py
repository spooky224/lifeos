import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.db.session import SessionLocal
from app.models.calendar_event import CalendarEventStatus
from app.repositories.calendar_events import CalendarEventRepository
from app.services.task_service import TaskService
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from app.graph.state import LifeOSState
from app.tools.calendar.get_events import get_calendar_events
from app.tools.calendar.find_available_slots import find_available_slots


load_dotenv()

LIFEOS_TIMEZONE = ZoneInfo("Africa/Tunis")


class TaskSelection(BaseModel):
    task_id: int | None = Field(
        description=(
            "ID of the task that best matches the user's reference, "
            "or null if no existing task clearly matches."
        )
    )


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


def _resolve_task_from_request(
    user_request: str,
    last_task_id: int | None = None,
) -> dict | None:
    """
    Identify an EXISTING task referenced in natural language.

    Used when the calendar agent is entered directly (the "calendar"
    intent — scheduling/rescheduling an existing task) rather than
    handed a task_context from the task agent in the same run.
    """

    session = SessionLocal()

    try:
        service = TaskService(session)

        # Deterministic short-circuit: "the last task" / "that task" /
        # "it" should mean whatever was just created or touched in
        # THIS thread, not a guess over the entire (unordered) task
        # table. Guessing here is how an unrelated task from months-old
        # test data ends up getting rescheduled.
        vague_reference = re.search(
            r"\b(last|previous|that|this|it)\b",
            user_request.lower(),
        )

        if vague_reference and last_task_id is not None:
            task = service.get_task(last_task_id)

            if task is not None:
                return {
                    "task_id": task.id,
                    "title": task.title,
                    "estimated_duration_minutes": task.estimated_duration_minutes,
                    "priority": task.priority,
                    "goal_id": task.goal_id,
                }

        tasks = service.list_tasks()

        if not tasks:
            return None

        # Sort most-recently-created first and say so explicitly —
        # without this, "last" is meaningless to the model, since a
        # flat list carries no recency signal at all.
        tasks = sorted(tasks, key=lambda t: t.id, reverse=True)

        identification_prompt = f"""
You are identifying an existing LIFEOS task referenced by the user.

User request:
{user_request}

Available tasks, MOST RECENTLY CREATED FIRST:
{[
    {"id": t.id, "title": t.title, "status": str(t.status)}
    for t in tasks
]}

If the user refers to "the last task", "that task", "it", or
similar, that means the FIRST task in the list above (most recent).

Return the ID of the task that best matches. If nothing clearly
matches, return null. Do not invent an ID.

Return ONLY valid JSON:
{{
    "task_id": 123
}}
"""

        selector = model.with_structured_output(
            TaskSelection,
            method="json_mode",
        )

        selection = selector.invoke(identification_prompt)

        if selection.task_id is None:
            return None

        task = service.get_task(selection.task_id)

        if task is None:
            return None

        return {
            "task_id": task.id,
            "title": task.title,
            "estimated_duration_minutes": task.estimated_duration_minutes,
            "priority": task.priority,
            "goal_id": task.goal_id,
        }

    finally:
        session.close()


def calendar_agent(state: LifeOSState) -> LifeOSState:
    pending_reschedule = state.get("pending_reschedule")
    intent = state.get("intent")

    # The "calendar" intent means: identify an EXISTING task from
    # THIS message. Never trust a leftover task_context from a
    # previous turn in the same thread — LangGraph's checkpointer
    # keeps it around, and reusing it silently causes duplicate
    # events on unrelated follow-up requests (e.g. "reschedule my
    # task please" reusing whatever was last scheduled).
    if pending_reschedule:
        task = state.get("task_context")
    elif intent == "calendar":
        task = _resolve_task_from_request(
            state["user_request"],
            last_task_id=state.get("last_task_id"),
        )
    else:
        # Arrived here via task_agent -> route_after_task in THIS
        # same run, so task_context was just set by us.
        task = state.get("task_context")

    if not pending_reschedule and not task:
        clarification = (
            "I couldn't tell which task you want to schedule. "
            "Could you name the task more specifically, or create "
            "it first if it doesn't exist yet?"
        )

        return {
            "proposed_actions": [],
            "final_response": clarification,
            "messages": state.get("messages", []) + [
                {
                    "role": "calendar_agent",
                    "content": clarification,
                }
            ],
        }

    if pending_reschedule:
        task_id = pending_reschedule["task_id"]
    else:
        task_id = task["task_id"]

    google_event_id = None
    calendar_event_id = None
    is_reschedule = bool(pending_reschedule)

    if not pending_reschedule and intent == "calendar":
        # This task may already have an active calendar event.
        # "Schedule/reschedule my X task" on an already-scheduled
        # task must UPDATE that event, not create a second one.
        session = SessionLocal()

        try:
            calendar_event_repository = CalendarEventRepository(session)
            existing_events = [
                e for e in calendar_event_repository.list_by_task(task_id)
                if e.status == CalendarEventStatus.SCHEDULED
            ]

            if existing_events:
                existing = existing_events[-1]
                calendar_event_id = existing.id
                google_event_id = existing.google_event_id
                is_reschedule = True

        finally:
            session.close()

    if pending_reschedule:
        calendar_event_id = pending_reschedule["calendar_event_id"]

        session = SessionLocal()

        try:
            calendar_event_repository = CalendarEventRepository(session)

            calendar_event = calendar_event_repository.get_by_id(
                calendar_event_id
            )

            if calendar_event is None:
                raise ValueError(
                    f"Calendar event #{calendar_event_id} not found."
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

Current date/time (Africa/Tunis): {now.isoformat()}

Original user request:
{state["user_request"]}

Task:
{task}

Available calendar slots:
{available_slots}

The user's original request may contain an explicit or relative
time expression (e.g. "in one hour", "tomorrow at 10am", "Friday
at 3pm"). If it does, compute the exact target start time relative
to the current date/time above, and select the available slot that
CONTAINS that target time.

If the user gave no time expression at all, select the earliest
available slot that is long enough.

If the user gave a time expression but no available slot contains
it (conflict with an existing event), select the closest available
slot to that requested time instead, and say so in the explanation.

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
        "last_task_id": task_id,
        "proposed_actions": [
            {
                "type": (
                    "reschedule_calendar_event"
                    if is_reschedule
                    else "create_calendar_event"
                ),
                "task_id": task_id,
                "calendar_event_id": calendar_event_id,
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