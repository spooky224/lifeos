import os
import re
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from app.agents.interrupt_utils import ask, TopicSwitchDetected

from app.db.session import SessionLocal
from app.graph.state import LifeOSState
from app.repositories.routines import RoutineRepository


load_dotenv()

LIFEOS_TIMEZONE = ZoneInfo("Africa/Tunis")


class RoutineContext(BaseModel):

    name: str = Field(
        description="Name of the routine."
    )

    description: str | None = Field(
        default=None,
        description="Short description of the routine."
    )

    frequency: str = Field(
        description="Routine frequency: daily, weekly, or monthly."
    )

    days_of_week: list[int] | None = Field(
        default=None,
        description=(
            "For weekly routines, Monday=0 through Sunday=6. "
            "For monthly routines, use day numbers 1-31. "
            "For daily routines, null."
        ),
    )

    preferred_time: str | None = Field(
        default=None,
        description="Preferred time in HH:MM 24-hour format.",
    )

    duration_minutes: int = Field(
        description="Duration of one occurrence in minutes."
    )

    priority: str = Field(
        description="Priority: low, medium, or high."
    )


model = ChatGroq(
    model=os.getenv("LIFEOS_MODEL"),
    temperature=0,
)

routine_model = model.with_structured_output(RoutineContext)


WEEKDAY_NAMES = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}


def _parse_days_of_week(text: str) -> list[int] | None:
    text = text.lower()

    days = sorted({
        value
        for name, value in WEEKDAY_NAMES.items()
        if re.search(rf"\b{name}\b", text)
    })

    return days or None


def _parse_month_days(text: str) -> list[int] | None:
    numbers = [
        int(n) for n in re.findall(r"\b(\d{1,2})\b", text)
        if 1 <= int(n) <= 31
    ]

    return numbers or None


class TimeExtraction(BaseModel):
    time_24h: str | None = Field(
        description=(
            "The time converted to 24-hour HH:MM format, "
            "or null if unclear."
        )
    )


def _parse_preferred_time(text: str) -> str | None:
    bare = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", text.strip())

    if bare:
        return text.strip()

    time_model = model.with_structured_output(
        TimeExtraction,
        method="json_mode",
    )

    try:
        result = time_model.invoke(f"""
Convert this time description to 24-hour HH:MM format.

Text: "{text}"

Examples:
"7pm" -> "19:00"
"7 in the evening" -> "19:00"
"half past 8 in the morning" -> "08:30"
"noon" -> "12:00"

Return ONLY valid JSON:
{{"time_24h": "19:00"}}
""")
        return result.time_24h
    except Exception:
        return None


def _build_recurrence_rule(
    frequency: str,
    days_of_week: list[int] | None,
) -> str:

    if frequency == "daily":
        return "RRULE:FREQ=DAILY"

    if frequency == "weekly":

        if not days_of_week:
            raise ValueError(
                "Weekly routines require at least one day."
            )

        day_codes = [
            "MO",
            "TU",
            "WE",
            "TH",
            "FR",
            "SA",
            "SU",
        ]

        codes = [
            day_codes[day]
            for day in days_of_week
        ]

        return f"RRULE:FREQ=WEEKLY;BYDAY={','.join(codes)}"

    if frequency == "monthly":

        if not days_of_week:
            raise ValueError(
                "Monthly routines require at least one day."
            )

        return (
            "RRULE:FREQ=MONTHLY;"
            f"BYMONTHDAY={','.join(str(day) for day in days_of_week)}"
        )

    raise ValueError(
        f"Unsupported routine frequency: {frequency}"
    )


def _get_next_occurrence(
    frequency: str,
    preferred_time: time,
    days_of_week: list[int] | None,
) -> datetime:

    now = datetime.now(LIFEOS_TIMEZONE)

    candidate = datetime.combine(
        now.date(),
        preferred_time,
        tzinfo=LIFEOS_TIMEZONE,
    )

    # DAILY
    if frequency == "daily":

        if candidate <= now:
            candidate += timedelta(days=1)

        return candidate

    # WEEKLY
    if frequency == "weekly":

        if not days_of_week:
            raise ValueError(
                "Weekly routines require days_of_week."
            )

        for offset in range(8):

            date_candidate = now.date() + timedelta(days=offset)

            if date_candidate.weekday() not in days_of_week:
                continue

            occurrence = datetime.combine(
                date_candidate,
                preferred_time,
                tzinfo=LIFEOS_TIMEZONE,
            )

            if occurrence > now:
                return occurrence

        raise ValueError(
            "Could not calculate next weekly occurrence."
        )

    # MONTHLY
    if frequency == "monthly":

        if not days_of_week:
            raise ValueError(
                "Monthly routines require day numbers."
            )

        for offset in range(0, 62):

            date_candidate = now.date() + timedelta(days=offset)

            if date_candidate.day not in days_of_week:
                continue

            occurrence = datetime.combine(
                date_candidate,
                preferred_time,
                tzinfo=LIFEOS_TIMEZONE,
            )

            if occurrence > now:
                return occurrence

        raise ValueError(
            "Could not calculate next monthly occurrence."
        )

    raise ValueError(
        f"Unsupported routine frequency: {frequency}"
    )


def _resolve_routine_schedule(
    result: "RoutineContext",
) -> tuple[time, str, datetime]:
    """
    Fill in whatever the extraction missed (time, days) by asking
    the user directly via interrupt(), instead of crashing. Returns
    the resolved preferred_time, recurrence_rule, and start_datetime.
    """

    preferred_time_str = result.preferred_time

    while not preferred_time_str:
        answer = ask(
            f"What time should '{result.name}' happen?"
        )
        preferred_time_str = _parse_preferred_time(answer)

    preferred_time = time.fromisoformat(preferred_time_str)

    days_of_week = result.days_of_week

    if result.frequency == "weekly":
        while not days_of_week:
            answer = ask(
                f"Which day(s) of the week should '{result.name}' "
                "happen on?"
            )
            days_of_week = _parse_days_of_week(answer)

    elif result.frequency == "monthly":
        while not days_of_week:
            answer = ask(
                f"Which day(s) of the month should '{result.name}' "
                "happen on (e.g. the 1st and 15th)?"
            )
            days_of_week = _parse_month_days(answer)

    recurrence_rule = _build_recurrence_rule(
        result.frequency,
        days_of_week,
    )

    start_datetime = _get_next_occurrence(
        result.frequency,
        preferred_time,
        days_of_week,
    )

    result.days_of_week = days_of_week

    return preferred_time, recurrence_rule, start_datetime


def routine_agent(state: LifeOSState) -> LifeOSState:

    user_request = state["user_request"]

    prompt = f"""
You are the Routine Agent of LIFEOS.

Your responsibility is to understand a user's request
to create a recurring personal routine.

Extract the routine information from the request.

Rules:

1. Identify a concise routine name.

2. Identify the frequency:
   - daily
   - weekly
   - monthly

3. For weekly routines:
   - Monday = 0
   - Tuesday = 1
   - Wednesday = 2
   - Thursday = 3
   - Friday = 4
   - Saturday = 5
   - Sunday = 6

4. For monthly routines, days_of_week contains
   day numbers 1-31.

5. For daily routines, days_of_week must be null.

6. Extract duration in minutes.

7. Extract preferred time when provided.

8. If the user gives a vague period:
   - morning → 08:00
   - afternoon → 14:00
   - evening → 19:00

9. If no priority is specified:
   use medium.

10. Do not invent unrelated information. Leave preferred_time
    or days_of_week null rather than guessing if the user
    genuinely didn't say.

User request:
{user_request}
"""

    try:
        result = routine_model.invoke(prompt)
    except Exception:
        clarification = (
            "I couldn't quite understand that routine. Could you "
            "rephrase it with what it is, how often, and roughly "
            "what time?"
        )
        return {
            "final_response": clarification,
            "messages": state.get("messages", []) + [
                {"role": "routine_agent", "content": clarification}
            ],
        }

    try:
        preferred_time, recurrence_rule, start_datetime = (
            _resolve_routine_schedule(result)
        )
    except TopicSwitchDetected as switch:
        return {
            "user_request": switch.new_request,
            "topic_switch": True,
        }

    end_datetime = (
        start_datetime
        + timedelta(minutes=result.duration_minutes)
    )

    session = SessionLocal()

    try:

        repository = RoutineRepository(session)

        routine = repository.create(
            name=result.name,
            description=result.description,
            frequency=result.frequency,
            days_of_week=result.days_of_week,
            preferred_time=preferred_time,
            duration_minutes=result.duration_minutes,
            priority=result.priority,
            goal_id=None,
        )

        # IMPORTANT:
        # The routine is only a pending proposal at this point.
        # It becomes active after human approval.
        routine.is_active = False

        session.commit()

        routine_context = {
            "routine_id": routine.id,
            "name": routine.name,
            "description": routine.description,
            "frequency": routine.frequency,
            "days_of_week": routine.days_of_week,
            "preferred_time": (
                routine.preferred_time.isoformat()
                if routine.preferred_time
                else None
            ),
            "duration_minutes": routine.duration_minutes,
            "priority": routine.priority,
            "recurrence_rule": recurrence_rule,
        }

        proposal = {
            "type": "create_recurring_calendar_event",
            "routine_id": routine.id,
            "title": routine.name,
            "start": start_datetime.isoformat(),
            "end": end_datetime.isoformat(),
            "recurrence": [recurrence_rule],
            "recurrence_rule": recurrence_rule,
            "explanation": (
                f"Schedule '{routine.name}' "
                f"every {routine.frequency} at "
                f"{preferred_time.strftime('%H:%M')} "
                f"for {routine.duration_minutes} minutes."
            ),
        }

        return {
            "routine_context": routine_context,
            "proposed_actions": [proposal],
            "pending_approval": True,
            "messages": state.get("messages", []) + [
                {
                    "role": "routine_agent",
                    "content": (
                        f"Prepared routine '{routine.name}' "
                        f"with frequency '{routine.frequency}', "
                        f"at {preferred_time.strftime('%H:%M')}, "
                        f"for {routine.duration_minutes} minutes."
                    ),
                }
            ],
        }

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()