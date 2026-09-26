from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.db.session import SessionLocal
from app.services.lifecycle_service import LifecycleService
from app.repositories.tasks import TaskRepository
from app.repositories.calendar_events import CalendarEventRepository
from app.models.task import TaskStatus


LIFEOS_TIMEZONE = ZoneInfo("Africa/Tunis")

session = SessionLocal()

try:
    task_repository = TaskRepository(session)
    calendar_repository = CalendarEventRepository(session)

    # Create controlled overdue task
    task = task_repository.create(
        goal_id=None,
        title="TEST - Overdue lifecycle task",
        estimated_duration_minutes=60,
    )

    task.status = TaskStatus.SCHEDULED
    session.flush()

    start_time = datetime.now(LIFEOS_TIMEZONE) - timedelta(hours=2)
    end_time = datetime.now(LIFEOS_TIMEZONE) - timedelta(hours=1)

    calendar_event = calendar_repository.create(
        task_id=task.id,
        routine_id=None,
        google_event_id="TEST_LIFECYCLE_EVENT",
        title=task.title,
        start_time=start_time,
        end_time=end_time,
    )

    session.commit()

    # Lifecycle inspection
    service = LifecycleService(session)

    print("\n=== LIFEOS LIFECYCLE INSPECTION ===")

    issues = service.inspect()

    for issue in issues:
        print(f"\n[{issue['type']}]")
        print(f"Task: {issue.get('task_id')}")
        print(f"Title: {issue.get('title')}")
        print(issue["message"])

    # Evaluate
    actions = service.evaluate()

    print("\n=== LIFECYCLE ACTIONS ===")

    for action in actions:
        print(f"\n[{action['type']}]")
        print(f"Task: {action['task_id']}")
        print(f"Requires user: {action['requires_user']}")
        print(action["message"])

finally:
    session.rollback()
    session.close()