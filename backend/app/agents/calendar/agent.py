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


# LIFEOS_CALENDAR_PROPOSAL_VALIDATION_V1

def _validate_calendar_proposal(
    proposed_start: str,
    proposed_end: str,
    available_slots: list[dict[str, str]],
    expected_duration_minutes: int | None,
    user_request: str,
    now: datetime,
) -> str | None:
    """Return a safety issue if the model's proposal violates known constraints."""
    try:
        start = datetime.fromisoformat(proposed_start)
        end = datetime.fromisoformat(proposed_end)
    except (TypeError, ValueError):
        return "the proposed start or end is not a valid ISO datetime"

    if start.tzinfo is None:
        start = start.replace(tzinfo=LIFEOS_TIMEZONE)
    else:
        start = start.astimezone(LIFEOS_TIMEZONE)
    if end.tzinfo is None:
        end = end.replace(tzinfo=LIFEOS_TIMEZONE)
    else:
        end = end.astimezone(LIFEOS_TIMEZONE)

    if end <= start:
        return "the end time is not later than the start time"

    actual_minutes = int((end - start).total_seconds() // 60)
    if expected_duration_minutes and actual_minutes != expected_duration_minutes:
        return (
            f"the proposal lasts {actual_minutes} minutes, but the task requires "
            f"{expected_duration_minutes} minutes"
        )

    local_now = now.astimezone(LIFEOS_TIMEZONE) if now.tzinfo else now.replace(tzinfo=LIFEOS_TIMEZONE)
    if start < local_now:
        return "the proposed start time is in the past"
    if end > local_now + timedelta(days=14, seconds=1):
        return "the proposal falls outside the calendar availability window"

    contained_in_free_slot = False
    for slot in available_slots:
        try:
            slot_start = datetime.fromisoformat(slot["start"])
            slot_end = datetime.fromisoformat(slot["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if slot_start.tzinfo is None:
            slot_start = slot_start.replace(tzinfo=LIFEOS_TIMEZONE)
        else:
            slot_start = slot_start.astimezone(LIFEOS_TIMEZONE)
        if slot_end.tzinfo is None:
            slot_end = slot_end.replace(tzinfo=LIFEOS_TIMEZONE)
        else:
            slot_end = slot_end.astimezone(LIFEOS_TIMEZONE)
        if slot_start <= start and end <= slot_end:
            contained_in_free_slot = True
            break
    if not contained_in_free_slot:
        return "the proposed time is not fully contained in a verified free calendar slot"

    request_lower = user_request.lower()

    # Honor an explicitly requested calendar week instead of silently using
    # any date in the wider rolling 14-day availability window.
    if re.search(r"\bthis week\b", request_lower):
        monday = local_now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=local_now.weekday())
        next_monday = monday + timedelta(days=7)
        if start < monday or end > next_monday:
            return "the proposed event is outside the current calendar week"
    elif re.search(r"\bnext week\b", request_lower):
        monday = local_now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=local_now.weekday()) + timedelta(days=7)
        next_monday = monday + timedelta(days=7)
        if start < monday or end > next_monday:
            return "the proposed event is outside next calendar week"

    # Check simple explicit clock boundaries such as "after 1 PM" or
    # "before 5:30 PM". Treat the boundary itself as acceptable for the
    # natural-language preference "after 1 PM".
    after_match = re.search(
        r"\bafter\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        request_lower,
    )
    if after_match:
        hour = int(after_match.group(1)) % 12
        if after_match.group(3) == "pm":
            hour += 12
        minute = int(after_match.group(2) or 0)
        boundary_minutes = hour * 60 + minute
        if start.hour * 60 + start.minute < boundary_minutes:
            return "the proposed start time is earlier than the requested time-of-day boundary"

    before_match = re.search(
        r"\bbefore\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
        request_lower,
    )
    if before_match:
        hour = int(before_match.group(1)) % 12
        if before_match.group(3) == "pm":
            hour += 12
        minute = int(before_match.group(2) or 0)
        boundary_minutes = hour * 60 + minute
        if end.hour * 60 + end.minute > boundary_minutes:
            return "the proposed end time is later than the requested time-of-day boundary"

    return None


class TaskSelection(BaseModel):
    task_id: int | None = Field(
        description=(
            "ID of the task that best matches the user's reference, "
            "or null if no existing task clearly matches."
        )
    )


class CalendarProposal(BaseModel):
    proposed_start: str | None = Field(
        default=None,
        description=(
            "Proposed start date and time in ISO format. Null if "
            "no available slot is long enough for the requested "
            "duration."
        ),
    )

    proposed_end: str | None = Field(
        default=None,
        description="Proposed end date and time in ISO format."
    )

    title: str = Field(
        description="Calendar event title."
    )

    explanation: str = Field(
        description="Why this time slot is appropriate, or why none fit."
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
    original_start = None
    original_end = None

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
                original_start = existing.start_time
                original_end = existing.end_time
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
            original_start = calendar_event.start_time
            original_end = calendar_event.end_time

        finally:
            session.close()

    now = datetime.now(LIFEOS_TIMEZONE)

    # Rolling 2-week scheduling window from "now" -- NOT "this
    # calendar week". A hardcoded Monday-Sunday window makes anything
    # near a week boundary invisible to the slot finder (e.g. a
    # Sunday request for "next Tuesday" would have no slots to pick
    # from at all).
    window_start = now
    window_end = now + timedelta(days=14)

    # Get REAL events only inside the scheduling window.
    events = get_calendar_events(
        start_datetime=window_start,
        end_datetime=window_end,
    )

    # Calculate REAL available slots.
    available_slots = find_available_slots(
        events=events,
        start_datetime=window_start,
        end_datetime=window_end,
    )

    calendar_context = {
        "timezone": "Africa/Tunis",
        "available_slots": available_slots,
    }

    original_time_context = (
        f"""
This is a RESCHEDULE of an existing event, originally scheduled:
{original_start.isoformat()} to {original_end.isoformat()}

If the user's request only mentions a TIME (e.g. "move it to 7pm")
with no date, keep the SAME DATE as the original ({original_start.date().isoformat()})
and only change the time. Only use a different date if the user
explicitly mentions one (e.g. "tomorrow", "next Monday", "Friday").
"""
        if is_reschedule and original_start
        else ""
    )

    prompt = f"""
You are the Calendar Agent of LIFEOS.

Current date/time (Africa/Tunis): {now.isoformat()}

Original user request:
{state["user_request"]}

Task:
{task}
{original_time_context}
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

    try:
        result = calendar_model.invoke(prompt)
    except Exception:
        clarification = (
            f"I couldn't find a way to schedule '{task['title']}' -- "
            "could you give a shorter duration or a different time?"
        )
        return {
            "last_task_id": task_id,
            "proposed_actions": [],
            "final_response": clarification,
            "messages": state.get("messages", []) + [
                {"role": "calendar_agent", "content": clarification}
            ],
        }

    if not result.proposed_start or not result.proposed_end:
        clarification = (
            f"I couldn't fit '{result.title}' into any available "
            f"slot. {result.explanation} Could you give a shorter "
            "duration or a different time frame?"
        )
        return {
            "last_task_id": task_id,
            "proposed_actions": [],
            "final_response": clarification,
            "messages": state.get("messages", []) + [
                {"role": "calendar_agent", "content": clarification}
            ],
        }

    validation_error = _validate_calendar_proposal(
        proposed_start=result.proposed_start,
        proposed_end=result.proposed_end,
        available_slots=available_slots,
        expected_duration_minutes=task.get("estimated_duration_minutes"),
        user_request=state["user_request"],
        now=now,
    )
    if validation_error:
        clarification = (
            "I found a possible time, but it did not pass my calendar safety checks: "
            f"{validation_error}. I have not added anything to your calendar. "
            "Would you like me to try another slot?"
        )
        return {
            "last_task_id": task_id,
            "proposed_actions": [],
            "final_response": clarification,
            "messages": state.get("messages", []) + [
                {"role": "calendar_agent", "content": clarification}
            ],
        }

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
                "title": task["title"],
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