from app.agents.interrupt_utils import ask, TopicSwitchDetected
from app.graph.state import LifeOSState
from app.db.session import SessionLocal
from app.services.task_service import TaskService
from app.services.calendar_service import CalendarService


def _normalize_lifecycle_decision(raw) -> str | None:
    text = str(raw).lower().strip()

    if "cancel" in text:
        return "cancel"
    if "miss" in text:
        return "missed"
    if "resched" in text or "postpone" in text or "delay" in text:
        return "reschedule"

    return None


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

    # Proactive path: the user's own message already stated the
    # decision (e.g. classified as "lifecycle" intent because they
    # said "cancel it") -- act on it immediately, no need to ask.
    decision = _normalize_lifecycle_decision(state.get("user_request", ""))

    try:
        if decision is None:
            decision = _normalize_lifecycle_decision(
                ask(action["message"])
            )

        while decision is None:
            decision = _normalize_lifecycle_decision(
                ask(
                    "I didn't catch that. Please reply with one of: "
                    "'missed', 'cancel', or 'reschedule'."
                )
            )

    except TopicSwitchDetected as switch:
        return {
            "user_request": switch.new_request,
            "topic_switch": True,
        }

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
            note = (
                f"Got it — task #{task_id} is cancelled from its old "
                "slot. When would you like to reschedule it?"
            )
            return {
                "approval_decision": decision,
                "pending_reschedule": {
                    "task_id": task_id,
                    "calendar_event_id": calendar_event_id,
                },
                "lifecycle_actions": [],
                "lifecycle_issues": [],
                "final_response": note,
                "messages": state.get("messages", []) + [
                    {"role": "supervisor_agent", "content": note}
                ],
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
            # Unreachable: _normalize_lifecycle_decision only ever
            # returns "missed", "cancel", "reschedule", or None (and
            # the loop above keeps asking until it's not None).
            raise AssertionError(f"Unexpected decision: {decision!r}")

        session.commit()

        note = f"Done — task #{task_id} has been marked as {decision}."

        return {
            "approval_decision": decision,
            "lifecycle_actions": [],
            "lifecycle_issues": [],
            "final_response": note,
            "messages": state.get("messages", []) + [
                {"role": "supervisor_agent", "content": note}
            ],
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