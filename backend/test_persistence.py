from datetime import datetime
from zoneinfo import ZoneInfo

from app.db.session import SessionLocal
from app.models import CalendarEvent, Goal, Task
from app.models.calendar_event import CalendarEventStatus
from app.models.goal import GoalStatus
from app.models.task import TaskStatus
from app.repositories import (
    CalendarEventRepository,
    GoalRepository,
    TaskRepository,
)


def main():
    session = SessionLocal()

    try:
        goal_repository = GoalRepository(session)
        task_repository = TaskRepository(session)
        calendar_event_repository = CalendarEventRepository(session)

        print("=== CREATE GOAL ===")

        goal = goal_repository.create(
            name="LIFEOS Persistence Test",
            description="Temporary goal for testing PostgreSQL persistence.",
            priority="high",
        )

        print(f"Goal created: id={goal.id}, name={goal.name}")

        print("\n=== CREATE TASK ===")

        task = task_repository.create(
            goal_id=goal.id,
            title="Test database persistence",
            description="Temporary task for the persistence integration test.",
            estimated_duration_minutes=60,
            priority="high",
        )

        print(f"Task created: id={task.id}, title={task.title}")

        print("\n=== CREATE CALENDAR EVENT ===")

        start_time = datetime(
            2026,
            9,
            20,
            9,
            0,
            tzinfo=ZoneInfo("Africa/Tunis"),
        )

        end_time = datetime(
            2026,
            9,
            20,
            10,
            0,
            tzinfo=ZoneInfo("Africa/Tunis"),
        )

        calendar_event = calendar_event_repository.create(
            task_id=task.id,
            google_event_id="lifeos-persistence-test-event",
            title=task.title,
            start_time=start_time,
            end_time=end_time,
        )

        print(
            f"Calendar event created: "
            f"id={calendar_event.id}, "
            f"google_event_id={calendar_event.google_event_id}"
        )

        print("\n=== VERIFY RELATIONSHIPS ===")

        stored_goal = goal_repository.get_by_id(goal.id)
        stored_task = task_repository.get_by_id(task.id)
        stored_event = calendar_event_repository.get_by_id(calendar_event.id)

        print(f"Goal found: {stored_goal is not None}")
        print(f"Task found: {stored_task is not None}")
        print(f"Calendar event found: {stored_event is not None}")

        print(
            f"Task belongs to goal: "
            f"{stored_task.goal_id == stored_goal.id}"
        )

        print(
            f"Calendar event belongs to task: "
            f"{stored_event.task_id == stored_task.id}"
        )

        print("\n=== UPDATE STATUS ===")

        task_repository.update_status(
            stored_task,
            TaskStatus.COMPLETED,
        )

        goal_repository.update_status(
            stored_goal,
            GoalStatus.COMPLETED,
        )

        calendar_event_repository.update_status(
            stored_event,
            CalendarEventStatus.COMPLETED,
        )

        print(f"Task status: {stored_task.status.value}")
        print(f"Goal status: {stored_goal.status.value}")
        print(f"Calendar event status: {stored_event.status.value}")

        session.commit()

        print("\n=== PERSISTENCE TEST PASSED ===")

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


if __name__ == "__main__":
    main()