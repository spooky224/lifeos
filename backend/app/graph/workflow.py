from datetime import datetime

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt

from app.tools.calendar.create_event import create_calendar_event
from app.services.google_calendar import update_event
from app.graph.state import LifeOSState

from app.db.session import SessionLocal

from app.repositories.calendar_events import (
    CalendarEventRepository,
)

from app.repositories.tasks import TaskRepository

from app.repositories.routines import RoutineRepository

from app.agents.personal.agent import personal_agent
from app.agents.companion_agent import companion_agent
from app.agents.goals.agent import goal_agent
from app.agents.calendar.agent import calendar_agent
from app.agents.routines.agent import routine_agent
from app.agents.tasks.agent import task_agent
from app.agents.lifecycle.agent import lifecycle_agent
from app.agents.supervisor.agent import supervisor_agent

from app.models.task import TaskStatus



def _format_approval_datetime(value: str) -> datetime:
    """Parse an ISO timestamp, including Z suffixes, for display only."""
    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    # LIFEOS stores/schedules in Africa/Tunis; the input timestamps are expected
    # to carry their timezone. Preserve the parsed instant for local display.
    return parsed

def _format_approval_slot(start_value: str, end_value: str) -> str:
    """Render ISO timestamps as a concise, friendly local date/time range."""
    start = _format_approval_datetime(start_value)
    end = _format_approval_datetime(end_value)
    date_label = start.strftime("%A, %B %-d, %Y")
    start_label = start.strftime("%-I:%M %p")
    end_label = end.strftime("%-I:%M %p")
    minutes = max(0, int((end - start).total_seconds() // 60))
    if minutes % 60 == 0:
        duration_label = f"{minutes // 60} hour" + ("s" if minutes != 60 else "")
    else:
        hours, remainder = divmod(minutes, 60)
        duration_label = (f"{hours} hour" + ("s" if hours != 1 else "") + " " if hours else "") + f"{remainder} minutes"
    return f"{date_label}\n{start_label} – {end_label} · {duration_label}"

def approval_node(state: LifeOSState) -> LifeOSState:
    proposal = state["proposed_actions"][0]
    proposal_type = proposal.get("type")
    slot_label = _format_approval_slot(proposal["start"], proposal["end"])

    if proposal_type == "create_recurring_calendar_event":
        approval_message = (
            "Here's the proposed recurring routine for your Google Calendar:\n\n"
            f"**{proposal['title']}**\n"
            f"{slot_label}\n"
            f"Repeats: {proposal['recurrence_rule']}\n\n"
            f"Why: {proposal['explanation']}\n\n"
            "Should I add it to your calendar? Nothing will be scheduled until you approve."
        )
    else:
        approval_message = (
            "Here's a time I'd recommend for your calendar:\n\n"
            f"**{proposal['title']}**\n"
            f"{slot_label}\n\n"
            f"Why this time: {proposal['explanation']}\n\n"
            "Should I add this event to your calendar? Nothing will be scheduled until you approve."
        )

    decision = interrupt(approval_message)
    return {
        "pending_approval": False,
        "approval_decision": decision,
        "approval_message": approval_message,
    }


def route_after_personal(state: LifeOSState):
    intent = state["intent"]

    if intent == "goal":
        return "goal_agent"

    if intent == "routine":
        return "routine_agent"

    if intent == "calendar":
        return "calendar_agent"

    if intent in ("task_create", "task_update"):
        return "task_agent"

    # Ordinary dialogue is a valid outcome, not a rejected action.
    return "conversation_agent"

def execute_calendar_action(
    state: LifeOSState,
) -> LifeOSState:

    proposal = state["proposed_actions"][0]

    proposal_type = proposal.get("type")

    # =========================================================
    # RECURRING ROUTINE EVENT
    # =========================================================

    if proposal_type == "create_recurring_calendar_event":

        execution_result = create_calendar_event(
            title=proposal["title"],
            start=proposal["start"],
            end=proposal["end"],
            recurrence=proposal["recurrence"],
        )

        session = SessionLocal()

        try:

            calendar_event_repository = (
                CalendarEventRepository(session)
            )

            routine_repository = RoutineRepository(session)

            routine = routine_repository.get_by_id(
                proposal["routine_id"]
            )

            if routine is None:
                raise ValueError(
                    f"Routine #{proposal['routine_id']} not found."
                )

            calendar_event = (
                calendar_event_repository.create(
                    task_id=None,
                    routine_id=proposal["routine_id"],
                    google_event_id=execution_result["event_id"],
                    title=proposal["title"],
                    start_time=datetime.fromisoformat(
                        proposal["start"]
                    ),
                    end_time=datetime.fromisoformat(
                        proposal["end"]
                    ),
                    recurrence_rule=proposal[
                        "recurrence_rule"
                    ],
                )
            )

            # The routine becomes active only after
            # the Google Calendar event was successfully created.
            routine = routine_repository.activate(
                routine
            )

            session.commit()

            execution_result["calendar_event_id"] = (
                calendar_event.id
            )

            execution_result["routine_id"] = (
                routine.id
            )

            execution_result["recurrence_rule"] = (
                proposal["recurrence_rule"]
            )

            return {
                "execution_results": [
                    execution_result
                ],
                "messages": (
                    state.get("messages", [])
                    + [
                        {
                            "role": "calendar_execution",
                            "content": (
                                f"Created recurring Google Calendar "
                                f"event '{proposal['title']}' "
                                f"for Routine #{routine.id}. "
                                f"Recurrence: "
                                f"{proposal['recurrence_rule']}."
                            ),
                        }
                    ]
                ),
            }

        except Exception:

            session.rollback()
            raise

        finally:

            session.close()

    # =========================================================
    # RESCHEDULE EXISTING TASK EVENT
    # =========================================================

    if proposal_type == "reschedule_calendar_event":

        execution_result = update_event(
            event_id=proposal["google_event_id"],
            title=proposal["title"],
            start=proposal["start"],
            end=proposal["end"],
        )

        session = SessionLocal()

        try:
            calendar_event_repository = CalendarEventRepository(session)
            task_repository = TaskRepository(session)

            calendar_event = calendar_event_repository.get_by_id(
                proposal["calendar_event_id"]
            )

            if calendar_event is None:
                raise ValueError(
                    f"Calendar event #{proposal['calendar_event_id']} not found."
                )

            task = task_repository.get_by_id(
                proposal["task_id"]
            )

            if task is None:
                raise ValueError(
                    f"Task #{proposal['task_id']} not found."
                )

            calendar_event.title = proposal["title"]
            calendar_event.start_time = datetime.fromisoformat(
                proposal["start"]
            )
            calendar_event.end_time = datetime.fromisoformat(
                proposal["end"]
            )

            task = task_repository.update_status(
                task,
                TaskStatus.SCHEDULED,
            )

            session.commit()

            execution_result["calendar_event_id"] = calendar_event.id
            execution_result["task_id"] = task.id

            return {
                "execution_results": [
                    execution_result
                ],
                "pending_reschedule": None,
                "messages": (
                    state.get("messages", [])
                    + [
                        {
                            "role": "calendar_execution",
                            "content": (
                                f"Rescheduled '{proposal['title']}' "
                                f"to {proposal['start']}."
                            ),
                        }
                    ]
                ),
            }

        except Exception:
            session.rollback()
            raise

        finally:
            session.close()
    # =========================================================
    # EXISTING ONE-TIME TASK EVENT
    # =========================================================

    execution_result = create_calendar_event(
        title=proposal["title"],
        start=proposal["start"],
        end=proposal["end"],
    )

    session = SessionLocal()

    try:

        calendar_event_repository = (
            CalendarEventRepository(session)
        )

        task_repository = TaskRepository(session)

        calendar_event = (
            calendar_event_repository.create(
                task_id=proposal["task_id"],
                google_event_id=execution_result["event_id"],
                title=proposal["title"],
                start_time=datetime.fromisoformat(
                    proposal["start"]
                ),
                end_time=datetime.fromisoformat(
                    proposal["end"]
                ),
            )
        )

        task = task_repository.get_by_id(
            proposal["task_id"]
        )

        if task is None:
            raise ValueError(
                f"Task #{proposal['task_id']} not found."
            )

        task = task_repository.update_status(
            task,
            TaskStatus.SCHEDULED,
        )

        session.commit()

        execution_result["calendar_event_id"] = (
            calendar_event.id
        )

        execution_result["task_id"] = (
            proposal["task_id"]
        )

        return {
            "execution_results": [
                execution_result
            ],
            "messages": (
                state.get("messages", [])
                + [
                    {
                        "role": "calendar_execution",
                        "content": (
                            f"Persisted as CalendarEvent "
                            f"#{calendar_event.id} "
                            f"for Task "
                            f"#{proposal['task_id']}. "
                            f"Task status updated to "
                            f"'{task.status}'."
                        ),
                    }
                ]
            ),
        }

    except Exception:

        session.rollback()
        raise

    finally:

        session.close()


def replan(state: LifeOSState) -> LifeOSState:

    proposal = (
        state.get("proposed_actions") or [{}]
    )[0]

    if proposal.get("type") == "create_recurring_calendar_event":

        # The routine remains inactive because it was never approved.
        message = (
            "The recurring routine was not added to "
            "Google Calendar."
        )

    else:

        message = (
            "The proposed calendar action was rejected."
        )

    return {
        "execution_results": [
            {
                "status": "cancelled",
                "message": message,
            }
        ],
        "messages": (
            state.get("messages", [])
            + [
                {
                    "role": "replan",
                    "content": message,
                }
            ]
        ),
    }


def route_after_approval(state: LifeOSState):

    if state["approval_decision"] == "approved":
        return "execute_calendar_action"

    return "replan"

def route_after_calendar(state: LifeOSState):
    if not state.get("proposed_actions"):
        # calendar_agent couldn't resolve a task and already
        # produced a final_response asking the user to clarify.
        return END

    return "approval"


def route_after_goal(state: LifeOSState):
    if state.get("schedule_requested", False):
        return "calendar_agent"

    return END


def route_after_task(state: LifeOSState):
    if (
        state["intent"] == "task_create"
        and state.get("schedule_requested", False)
    ):
        return "calendar_agent"

    return END



def route_start(state: LifeOSState):
    # A notification's "Reschedule" button hands a specific task to the
    # chat. /chat sets pending_reschedule for that request only, so this
    # is deterministic: no intent guessing needed.
    if state.get("pending_reschedule"):
        return "calendar_agent"

    return "personal_agent"
def build_graph():

    graph = StateGraph(LifeOSState)

    # =========================================================
    # AGENTS
    # =========================================================

    graph.add_node(
        "personal_agent",
        personal_agent,
    )

    graph.add_node(
        "conversation_agent",
        companion_agent,
    )

    graph.add_node(
        "goal_agent",
        goal_agent,
    )

    graph.add_node(
        "routine_agent",
        routine_agent,
    )

    graph.add_node(
        "calendar_agent",
        calendar_agent,
    )
    
    graph.add_node(
        "task_agent",
        task_agent,
    )
    


    # =========================================================
    # HUMAN APPROVAL
    # =========================================================

    graph.add_node(
        "approval",
        approval_node,
    )

    # =========================================================
    # ACTIONS
    # =========================================================

    graph.add_node(
        "execute_calendar_action",
        execute_calendar_action,
    )

    graph.add_node(
        "replan",
        replan,
    )

    # =========================================================
    # START
    # =========================================================

    graph.add_conditional_edges(
        START,
        route_start,
        {
            "calendar_agent": "calendar_agent",
            "personal_agent": "personal_agent",
        },
    )
    # =========================================================
    # PERSONAL AGENT ROUTING
    # =========================================================
    
    graph.add_conditional_edges(
        "personal_agent",
        route_after_personal,
        {
            "goal_agent": "goal_agent",
            "routine_agent": "routine_agent",
            "calendar_agent": "calendar_agent",
            "task_agent": "task_agent",
            "conversation_agent": "conversation_agent",
            "replan": "replan",
        },
    )

    # =========================================================
    # GOAL → CALENDAR (or END if scheduling wasn't requested)
    # =========================================================

    graph.add_conditional_edges(
        "goal_agent",
        route_after_goal,
        {
            "calendar_agent": "calendar_agent",
            END: END,
        },
    )

    # =========================================================
    # ROUTINE → APPROVAL
    # =========================================================

    graph.add_edge(
        "routine_agent",
        "approval",
    )

    # =========================================================
    # CALENDAR → APPROVAL (or END if clarification is needed)
    # =========================================================

    graph.add_conditional_edges(
        "calendar_agent",
        route_after_calendar,
        {
            "approval": "approval",
            END: END,
        },
    )

    # =========================================================
    # APPROVAL ROUTING
    # =========================================================

    graph.add_conditional_edges(
        "approval",
        route_after_approval,
        {
            "execute_calendar_action":
                "execute_calendar_action",

            "replan":
                "replan",
        },
    )

    # =========================================================
    # END STATES
    # =========================================================

    graph.add_edge(
        "execute_calendar_action",
        END,
    )
    
    graph.add_conditional_edges(
        "task_agent",
        route_after_task,
        {
            "calendar_agent": "calendar_agent",
            END: END,
        },
    )

    graph.add_edge(
        "conversation_agent",
        END,
    )

    graph.add_edge(
        "replan",
        END,
    )

    checkpointer = InMemorySaver()

    compiled_graph = graph.compile(
        checkpointer=checkpointer
    )

    return compiled_graph