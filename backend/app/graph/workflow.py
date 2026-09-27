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
from app.agents.goals.agent import goal_agent
from app.agents.calendar.agent import calendar_agent
from app.agents.routines.agent import routine_agent
from app.agents.tasks.agent import task_agent
from app.agents.lifecycle.agent import lifecycle_agent
from app.agents.supervisor.agent import supervisor_agent

from app.models.task import TaskStatus


def approval_node(state: LifeOSState) -> LifeOSState:

    proposal = state["proposed_actions"][0]

    proposal_type = proposal.get("type")

    if proposal_type == "create_recurring_calendar_event":

        approval_message = (
            "Okay, I’ll set this recurring routine on your "
            "Google Calendar:\n\n"
            f"Routine: {proposal['title']}\n"
            f"Start: {proposal['start']}\n"
            f"End: {proposal['end']}\n"
            f"Recurrence: {proposal['recurrence_rule']}\n\n"
            f"Reason: {proposal['explanation']}\n\n"
            "Should I add it to your calendar?"
        )

    else:

        approval_message = (
            "Should I add this event to your calendar?\n\n"
            f"Title: {proposal['title']}\n"
            f"Start: {proposal['start']}\n"
            f"End: {proposal['end']}\n\n"
            f"Reason: {proposal['explanation']}"
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

    return "replan"

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


def route_after_task(state: LifeOSState):
    if (
        state["intent"] == "task_create"
        and state.get("schedule_requested", False)
    ):
        return "calendar_agent"

    return END


def route_after_lifecycle(state: LifeOSState):
    actions = state.get("lifecycle_actions", [])

    if any(action.get("requires_user") for action in actions):
        return "supervisor_agent"

    return "personal_agent"

def route_after_supervisor(state: LifeOSState):
    return END

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
    
    graph.add_node(
        "lifecycle_agent",
        lifecycle_agent,
    )
    
    graph.add_node(
        "supervisor_agent",
        supervisor_agent,
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

    graph.add_edge(START, "lifecycle_agent")

    graph.add_conditional_edges(
        "lifecycle_agent",
        route_after_lifecycle,
        {
            "supervisor_agent": "supervisor_agent",
            "personal_agent": "personal_agent",
        },
    )

    graph.add_conditional_edges(
        "supervisor_agent",
        route_after_supervisor,
        {
            "personal_agent": "personal_agent",
            END: END,
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
            "replan": "replan",
        },
    )

    # =========================================================
    # GOAL → CALENDAR
    # =========================================================

    graph.add_edge(
        "goal_agent",
        "calendar_agent",
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
        "replan",
        END,
    )

    checkpointer = InMemorySaver()

    compiled_graph = graph.compile(
        checkpointer=checkpointer
    )

    return compiled_graph