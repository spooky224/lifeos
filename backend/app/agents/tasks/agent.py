import os
import re
from datetime import datetime

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from app.agents.interrupt_utils import ask, TopicSwitchDetected
from app.db.session import SessionLocal
from app.graph.state import LifeOSState
from app.models.task import TaskStatus
from app.services.task_service import TaskService

load_dotenv()


class DurationExtraction(BaseModel):
    minutes: int | None = Field(
        description=(
            "The duration described in the text, converted to a "
            "whole number of minutes. Null if no duration is stated."
        )
    )


def _parse_duration_minutes(text: str) -> int | None:
    text = text.strip()

    bare_number = re.fullmatch(r"(\d+)", text)
    if bare_number:
        return int(bare_number.group(1))

    duration_model = model.with_structured_output(
        DurationExtraction,
        method="json_mode",
    )

    try:
        result = duration_model.invoke(f"""
Convert this duration description to a whole number of minutes.

Text: "{text}"

Examples:
"1 hour" -> 60
"1h30" -> 90
"1h30minutes approximately" -> 90
"an hour and a half" -> 90
"45 mins" -> 45
"half an hour" -> 30

Return ONLY valid JSON:
{{"minutes": 90}}
""")
        return result.minutes
    except Exception:
        return None


class TaskOperationContext(BaseModel):
    operation: str = Field(
        description="Must be either create or update."
    )
    task_reference: str | None = Field(
        default=None,
        description="Reference to an existing task when updating."
    )
    title: str | None = None
    estimated_duration_minutes: int | None = None
    priority: str | None = None
    description: str | None = None
    status: str | None = None
    reasoning: str
    schedule_requested: bool = False


model = ChatGroq(
    model=os.getenv("LIFEOS_MODEL"),
    temperature=0,
)

task_model = model.with_structured_output(
    TaskOperationContext,
    method="json_mode",
)


def task_agent(state: LifeOSState) -> LifeOSState:
    user_request = state["user_request"]
    intent = state["intent"]

    # ---------------------------------------------------------
    # CREATE TASK
    # ---------------------------------------------------------
    if intent == "task_create":
        prompt = f"""
You are the Task Agent of LIFEOS.

The user wants to create a ONE-TIME task.

Extract:

- title
- estimated duration in minutes
- priority
- optional description

Do not invent information.

Examples:

"I need to study Python for 2 hours tomorrow."
→ title: "Study Python"
→ duration: 120

"Create a task to prepare my presentation."
→ title: "Prepare my presentation"

User request:
{user_request}

- optional description

Schedule intent:
- Set schedule_requested to true when the user gives a concrete time or temporal constraint for the task.
- Examples:
  "in one hour" → true
  "tomorrow at 10am" → true
  "Friday at 3pm" → true
  "next Monday morning" → true
- Set it to false only when no scheduling information is provided.
Return ONLY valid JSON:

{{
    "operation": "create",
    "task_reference": null,
    "title": "...",
    "estimated_duration_minutes": 60,
    "priority": "medium",
    "description": null,
    "status": null,
    "schedule_requested": true,
    "reasoning": "..."
}}
"""

        try:
            result = task_model.invoke(prompt)
        except Exception:
            clarification = (
                "I couldn't quite parse that task request. Could you "
                "rephrase it with a clear title, and how long it should "
                "take?"
            )
            return {
                "schedule_requested": False,
                "final_response": clarification,
                "messages": state.get("messages", []) + [
                    {"role": "task_agent", "content": clarification}
                ],
            }

        try:
            if not result.title:
                answer = ask(
                    "What should I call this task? I couldn't tell "
                    "from your message."
                )
                result.title = answer.strip()

            while not result.estimated_duration_minutes:
                answer = ask(
                    f"How long should '{result.title}' take?"
                )
                result.estimated_duration_minutes = (
                    _parse_duration_minutes(answer)
                )

        except TopicSwitchDetected as switch:
            return {
                "user_request": switch.new_request,
                "topic_switch": True,
                "schedule_requested": False,
            }

        priority = result.priority or "medium"

        session = SessionLocal()

        try:
            service = TaskService(session)

            task = service.create_task(
                title=result.title,
                estimated_duration_minutes=result.estimated_duration_minutes,
                description=result.description,
                priority=priority,
            )

            session.commit()

            message = (
                f"Created task '{task.title}' "
                f"({task.estimated_duration_minutes} minutes)."
            )

            return {
                "task_context": {
                    "task_id": task.id,
                    "title": task.title,
                    "estimated_duration_minutes":
                        task.estimated_duration_minutes,
                    "priority": task.priority,
                    "goal_id": task.goal_id,
                },
                "last_task_id": task.id,
                "schedule_requested": result.schedule_requested,
                "messages": (
                    state.get("messages", [])
                    + [
                        {
                            "role": "task_agent",
                            "content": message,
                        }
                    ]
                ),
                "final_response": message,
            }

        except Exception:
            session.rollback()
            raise

        finally:
            session.close()

    # ---------------------------------------------------------
    # UPDATE TASK
    # ---------------------------------------------------------
    prompt = f"""
You are the Task Agent of LIFEOS.

The user wants to update an existing task.

Interpret:

- "I finished my AI project"
  -> completed

- "I didn't do my workout"
  -> missed

- "I postponed my AI project"
  -> postponed

- "I'm working on my AI project"
  -> in_progress

- "cancel my AI project" / "cancel it" / "I don't want to do this
  anymore" / "scrap that task"
  -> cancelled

Note the difference: "missed" means the user didn't do it but it
still should have happened (a failure/lapse). "cancelled" means the
user no longer wants to do it at all (a deliberate choice to drop
it). Do not default to "missed" when the user is clearly choosing
to cancel/drop/scrap something.

Identify the task reference.

User request:
{user_request}

Return ONLY valid JSON:

{{
    "operation": "update",
    "task_reference": "...",
    "title": null,
    "estimated_duration_minutes": null,
    "priority": "medium",
    "description": null,
    "status": "completed | missed | postponed | in_progress | cancelled",
    "reasoning": "..."
}}
"""

    try:
        result = task_model.invoke(prompt)
    except Exception:
        clarification = (
            "I couldn't quite understand that update. Could you "
            "rephrase which task, and what happened to it?"
        )
        return {
            "final_response": clarification,
            "messages": state.get("messages", []) + [
                {"role": "task_agent", "content": clarification}
            ],
        }

    session = SessionLocal()

    try:
        service = TaskService(session)

        tasks = service.list_tasks()

        if not tasks:
            clarification = (
                "You don't have any tasks yet, so there's nothing "
                "to update. Want to create one?"
            )
            return {
                "final_response": clarification,
                "messages": state.get("messages", []) + [
                    {"role": "task_agent", "content": clarification}
                ],
            }

        identification_prompt = f"""
You are identifying an existing LIFEOS task.

User request:
{user_request}

Available tasks:
{[
    {"id": task.id, "title": task.title, "status": str(task.status)}
    for task in tasks
]}

Return the ID of the task that best matches the user's reference.
If nothing clearly matches, return null. Do not invent an ID.

Return ONLY valid JSON:

{{
    "task_id": 123
}}
"""

        class TaskSelection(BaseModel):
            task_id: int | None = None

        selector = model.with_structured_output(
            TaskSelection,
            method="json_mode",
        )

        selection = selector.invoke(identification_prompt)
        task = (
            service.get_task(selection.task_id)
            if selection.task_id is not None
            else None
        )

        try:
            while task is None:
                answer = ask(
                    "I couldn't tell which task you mean. Could you "
                    "name it more specifically?"
                )
                reselection = selector.invoke(f"""
You are identifying an existing LIFEOS task.

User's clarification:
{answer}

Available tasks:
{[
    {"id": t.id, "title": t.title, "status": str(t.status)}
    for t in tasks
]}

Return the ID of the task that best matches. If nothing clearly
matches, return null. Do not invent an ID.

Return ONLY valid JSON:
{{"task_id": 123}}
""")
                task = (
                    service.get_task(reselection.task_id)
                    if reselection.task_id is not None
                    else None
                )

        except TopicSwitchDetected as switch:
            return {
                "user_request": switch.new_request,
                "topic_switch": True,
            }

        try:
            new_status = TaskStatus(result.status)
        except (ValueError, TypeError):
            clarification = (
                f"What actually happened with '{task.title}'? "
                "(completed, missed, postponed, cancelled, or in progress)"
            )
            return {
                "final_response": clarification,
                "messages": state.get("messages", []) + [
                    {"role": "task_agent", "content": clarification}
                ],
            }

        try:
            if new_status == TaskStatus.IN_PROGRESS:
                task = service.start_task(task.id)

            elif new_status == TaskStatus.COMPLETED:
                task = service.complete_task(task.id)

            else:
                task = service.update_status(task, new_status)

        except ValueError as exc:
            # An invalid transition (e.g. cancelling an already-
            # completed task) is a normal outcome to explain, not a
            # crash.
            clarification = str(exc)
            return {
                "final_response": clarification,
                "messages": state.get("messages", []) + [
                    {"role": "task_agent", "content": clarification}
                ],
            }

        session.commit()

        message = (
            f"Task '{task.title}' updated to "
            f"'{task.status}'."
        )

        return {
            "last_task_id": task.id,
            "execution_results": [
                {
                    "type": "task_status_update",
                    "task_id": task.id,
                    "status": task.status,
                }
            ],
            "messages": (
                state.get("messages", [])
                + [
                    {
                        "role": "task_agent",
                        "content": message,
                    }
                ]
            ),
            "final_response": message,
        }

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()