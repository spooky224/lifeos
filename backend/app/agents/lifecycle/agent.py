from app.graph.state import LifeOSState
from app.db.session import SessionLocal
from app.services.lifecycle_service import LifecycleService


def lifecycle_agent(state: LifeOSState) -> dict:
    
    """
    Runs lifecycle inspection and executes safe automatic cleanup.
    """
    if state.get("pending_reschedule"):
        return {
            "lifecycle_issues": [],
            "lifecycle_actions": [],
        }

    session = SessionLocal()

    try:
        service = LifecycleService(session)

        issues = service.inspect()
        actions = service.evaluate()

        removed_event_ids = service.cleanup_stale_calendar_events()

        if removed_event_ids:
            session.commit()

        return {
            "lifecycle_issues": issues,
            "lifecycle_actions": actions,
            "execution_results": [
                {
                    "type": "lifecycle_cleanup",
                    "removed_calendar_event_ids": removed_event_ids,
                }
            ],
        }

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()