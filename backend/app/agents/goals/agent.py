import os
import re

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from app.db.session import SessionLocal
from app.graph.state import LifeOSState
from app.models.task import TaskStatus
from app.repositories.goals import GoalRepository
from app.services.goal_service import GoalService
from app.services.task_service import TaskService

load_dotenv()


class GoalContext(BaseModel):
    operation: str = Field(
        description=(
            "'create_task' if the user wants to define a new goal or "
            "add/do work toward one. 'query' if they're asking about "
            "existing progress or status (e.g. 'what's left on my AI "
            "project', 'show me my goals', 'how is my fitness goal "
            "going')."
        )
    )
    goal_name: str = Field(
        description=(
            "The goal or project the user is referring to. For a "
            "general query with no specific goal named (e.g. 'show "
            "me all my goals'), use 'all'."
        )
    )
    task_description: str | None = Field(
        default=None,
        description=(
            "The specific work the user wants to add, when operation "
            "is create_task. Null for a query."
        ),
    )
    estimated_duration_minutes: int | None = Field(
        default=None,
        description=(
            "The length of a SINGLE work session for this task, in "
            "minutes (e.g. 30, 60, 120). This is NOT the time until "
            "a deadline -- a goal like 'lose 10kg by next month' "
            "still gets a normal session length like 60, not the "
            "number of minutes until next month. Null for a query."
        ),
    )
    deadline: str | None = Field(
        default=None,
        description=(
            "A target date/deadline for the overall GOAL, if one "
            "was mentioned (e.g. 'by the end of next month'). This "
            "is informational only and does NOT mean the task "
            "should be scheduled on the calendar now."
        ),
    )
    priority: str = Field(
        default="medium",
        description="Estimated priority: low, medium, or high."
    )
    schedule_requested: bool = Field(
        default=False,
        description=(
            "True ONLY if the user explicitly asked to schedule "
            "this task, place it on the calendar, or start working "
            "on it at a SPECIFIC time (e.g. 'schedule this for "
            "tomorrow at 3pm', 'put this on my calendar'). "
            "A deadline or target date for the overall goal (e.g. "
            "'by the end of next month', 'within 2 weeks') is NOT "
            "a scheduling request -- leave this false for those."
        ),
    )


class GoalSelection(BaseModel):
    goal_id: int | None = Field(
        description=(
            "ID of the EXISTING goal this refers to, or null if "
            "this is a genuinely new/different goal."
        )
    )


model = ChatGroq(
    model=os.getenv("LIFEOS_MODEL"),
    temperature=0,
)

goal_model = model.with_structured_output(GoalContext, method="json_mode")


def _resolve_goal(
    goal_name: str,
    user_request: str,
    last_goal_id: int | None,
    session,
):
    """
    Find an EXISTING goal this request refers to, or return None if
    it's genuinely a new one. Without this, every mention of a known
    goal ("add another task to my AI project") would silently create
    a second, duplicate goal instead of extending the existing one.
    """

    goal_repository = GoalRepository(session)
    goals = goal_repository.list_active()

    if not goals:
        return None

    vague_reference = re.search(
        r"\b(last|previous|that|this|it)\b",
        user_request.lower(),
    )

    if vague_reference and last_goal_id is not None:
        goal = goal_repository.get_by_id(last_goal_id)
        if goal is not None:
            return goal

    lowered_name = goal_name.lower().strip()

    for goal in goals:
        if goal.name.lower().strip() == lowered_name:
            return goal

    selector = model.with_structured_output(
        GoalSelection,
        method="json_mode",
    )

    prompt = f"""
Does this refer to one of the user's EXISTING goals, or is it a
genuinely new/different goal?

Extracted goal name: "{goal_name}"
User request: "{user_request}"

Existing goals:
{[{"id": g.id, "name": g.name} for g in goals]}

Return the ID of the existing goal it matches, or null if this is
a new, unrelated goal. Do not force a match if the topic differs.

Return ONLY valid JSON:
{{"goal_id": 123}}
"""

    try:
        selection = selector.invoke(prompt)
    except Exception:
        return None

    if selection.goal_id is None:
        return None

    return goal_repository.get_by_id(selection.goal_id)


def goal_agent(state: LifeOSState) -> LifeOSState:
    user_request = state["user_request"]

    prompt = f"""
You are the Goal Agent of LIFEOS.

Your responsibility is to understand the goal or project
behind the user's request.

First decide the operation:
- "create_task": the user wants to define a new goal, or add/do
  work toward one (including adding another task to a goal they
  already have).
- "query": the user is asking about existing progress or status,
  not asking you to create anything.

Then identify:
1. The goal/project involved (use "all" if the query has no
   specific goal named).
2. For create_task: the specific task, a reasonable single
   work-session duration (NOT time until a deadline), and priority.
3. A deadline for the overall goal, if mentioned (informational only).

Do not invent deadlines or facts that are not present.
A deadline or target date for the GOAL (e.g. "by next month") is
never, by itself, a scheduling request. Only set schedule_requested
to true if the user explicitly asked to schedule/calendar this task
or gave a SPECIFIC time to start working on it.

User request:
{user_request}

Return ONLY valid JSON, matching exactly this structure:

{{
  "operation": "create_task",
  "goal_name": "...",
  "task_description": "...",
  "estimated_duration_minutes": 60,
  "deadline": null,
  "priority": "medium",
  "schedule_requested": false
}}
"""

    try:
        result = goal_model.invoke(prompt)
    except Exception:
        clarification = (
            "I couldn't quite understand that goal. Could you "
            "rephrase it with what you want to accomplish and "
            "roughly how long it should take?"
        )
        return {
            "final_response": clarification,
            "messages": state.get("messages", []) + [
                {"role": "goal_agent", "content": clarification}
            ],
        }

    session = SessionLocal()

    try:
        matched_goal = None

        if result.goal_name.strip().lower() != "all":
            matched_goal = _resolve_goal(
                result.goal_name,
                user_request,
                state.get("last_goal_id"),
                session,
            )

        # -----------------------------------------------------
        # QUERY: report status, create nothing.
        # -----------------------------------------------------
        if result.operation == "query":
            goal_repository = GoalRepository(session)

            if matched_goal is None:
                goals = goal_repository.list_active()

                if not goals:
                    note = (
                        "You don't have any active goals yet. Want "
                        "to set one?"
                    )
                else:
                    lines = []
                    for goal in goals:
                        tasks = TaskService(session).list_tasks()
                        goal_tasks = [
                            t for t in tasks if t.goal_id == goal.id
                        ]
                        open_count = sum(
                            1 for t in goal_tasks
                            if t.status not in (
                                TaskStatus.COMPLETED,
                                TaskStatus.CANCELLED,
                            )
                        )
                        lines.append(
                            f"- {goal.name}: {open_count} open task(s) "
                            f"of {len(goal_tasks)}"
                        )
                    note = "Here's where your goals stand:\n" + "\n".join(
                        lines
                    )

                return {
                    "final_response": note,
                    "messages": state.get("messages", []) + [
                        {"role": "goal_agent", "content": note}
                    ],
                }

            tasks = TaskService(session).list_tasks()
            goal_tasks = [
                t for t in tasks if t.goal_id == matched_goal.id
            ]
            open_tasks = [
                t for t in goal_tasks
                if t.status not in (
                    TaskStatus.COMPLETED,
                    TaskStatus.CANCELLED,
                )
            ]

            if not goal_tasks:
                note = (
                    f"'{matched_goal.name}' doesn't have any tasks "
                    "yet. Want to add one?"
                )
            elif not open_tasks:
                note = (
                    f"Everything on '{matched_goal.name}' is done -- "
                    f"all {len(goal_tasks)} task(s) are complete."
                )
            else:
                lines = [
                    f"- {t.title} ({t.status.value if hasattr(t.status, 'value') else t.status})"
                    for t in open_tasks
                ]
                note = (
                    f"'{matched_goal.name}' has {len(open_tasks)} "
                    f"open task(s) out of {len(goal_tasks)}:\n"
                    + "\n".join(lines)
                )

            return {
                "last_goal_id": matched_goal.id,
                "final_response": note,
                "messages": state.get("messages", []) + [
                    {"role": "goal_agent", "content": note}
                ],
            }

        # -----------------------------------------------------
        # CREATE_TASK
        # -----------------------------------------------------
        if not result.task_description:
            clarification = (
                f"What specific task should I add toward "
                f"'{result.goal_name}'?"
            )
            return {
                "final_response": clarification,
                "messages": state.get("messages", []) + [
                    {"role": "goal_agent", "content": clarification}
                ],
            }

        if (
            not result.estimated_duration_minutes
            or result.estimated_duration_minutes > 480
        ):
            result.estimated_duration_minutes = 60

        if matched_goal is not None:
            # Existing goal: add a task to it. Do NOT create a new
            # Goal row -- that's the bug that made every follow-up
            # mention of a goal spawn a duplicate.
            task = TaskService(session).create_task(
                title=result.task_description,
                estimated_duration_minutes=result.estimated_duration_minutes,
                priority=result.priority,
                goal_id=matched_goal.id,
            )
            goal = matched_goal
            note = (
                f"Added '{result.task_description}' to your existing "
                f"goal '{goal.name}' (task_id={task.id})."
            )

        else:
            goal_service = GoalService(session)

            persisted = goal_service.create_goal_with_task(
                goal_name=result.goal_name,
                task_description=result.task_description,
                estimated_duration_minutes=result.estimated_duration_minutes,
                priority=result.priority,
            )

            goal = persisted["goal"]
            task = persisted["task"]
            note = (
                f"Identified goal: {result.goal_name}. "
                f"Task: {result.task_description}. "
                f"Persisted goal_id={goal.id}, task_id={task.id}."
            )

        session.commit()

        return {
            "goal_context": {
                "goal_name": goal.name,
                "task_description": result.task_description,
                "estimated_duration_minutes": result.estimated_duration_minutes,
                "priority": result.priority,
                "goal_id": goal.id,
                "task_id": task.id,
            },
            "task_context": {
                "task_id": task.id,
                "title": task.title,
                "estimated_duration_minutes": task.estimated_duration_minutes,
                "priority": task.priority,
                "goal_id": goal.id,
            },
            "last_task_id": task.id,
            "last_goal_id": goal.id,
            "schedule_requested": result.schedule_requested,
            "messages": state.get("messages", []) + [
                {"role": "goal_agent", "content": note}
            ],
        }

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()