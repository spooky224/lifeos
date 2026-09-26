from langgraph.types import interrupt

from app.graph.state import LifeOSState
from app.db.session import SessionLocal
from app.services.task_service import TaskService
from app.services.calendar_service import CalendarService


def supervisor_agent(state: LifeOSState) -> dict:
    """
    Handles lifecycle situations that require a user decision.
    """

    actions = state.get("lifecycle_actions", [])

    user_actions = [
        action
        for action in actions
        if action.get("requires_user")
    ]

    if not user_actions:
        return {}

    action = user_actions[0]

    decision = interrupt({
        "type": "lifecycle_decision",
        "task_id": action["task_id"],
        "calendar_event_id": action.get("calendar_event_id"),
        "message": action["message"],
    })

    decision = str(decision).lower().strip()

    session = SessionLocal()

    try:
        task_service = TaskService(session)
        calendar_service = CalendarService(session)

        task_id = action["task_id"]
        calendar_event_id = action.get("calendar_event_id")

        if decision == "missed":
            task_service.update_status_by_id(
                task_id,
                "missed",
            )

            if calendar_event_id:
                calendar_service.remove_event(calendar_event_id)

        elif decision == "cancel":
            task_service.update_status_by_id(
                task_id,
                "cancelled",
            )

            if calendar_event_id:
                calendar_service.remove_event(calendar_event_id)
        elif decision == "reschedule":
            return {
                "approval_decision": decision,
                "pending_reschedule": {
                    "task_id": task_id,
                    "calendar_event_id": calendar_event_id,
                },
                "lifecycle_actions": [],
                "lifecycle_issues": [],
                "execution_results": [{
                    "type": "lifecycle_reschedule_required",
                    "task_id": task_id,
                    "message": (
                        f"Task #{task_id} needs a new date and time. "
                        "Ask the user when they want to reschedule it."
                    ),
                }],
            }

        else:
            raise ValueError(
                f"Unknown lifecycle decision: '{decision}'."
            )

        session.commit()

        return {
            "approval_decision": decision,
            "lifecycle_actions": [],
            "lifecycle_issues": [],
            "execution_results": [{
                "type": "lifecycle_decision_executed",
                "task_id": task_id,
                "calendar_event_id": calendar_event_id,
                "decision": decision,
            }],
        }

    except Exception:
        session.rollback()
        raise

    finally:
        session.close() 