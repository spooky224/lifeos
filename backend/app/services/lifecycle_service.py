from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.task import TaskStatus
from app.repositories.tasks import TaskRepository
from app.repositories.calendar_events import CalendarEventRepository


LIFEOS_TIMEZONE = ZoneInfo("Africa/Tunis")


class LifecycleService:
    """
    Detects inconsistencies and lifecycle situations across
    Tasks and CalendarEvents.

    This service does not use an LLM and does not automatically
    modify anything yet.
    """

    def __init__(self, session: Session):
        self.session = session
        self.task_repository = TaskRepository(session)
        self.calendar_event_repository = CalendarEventRepository(session)

    def inspect(self) -> list[dict]:
        now = datetime.now(LIFEOS_TIMEZONE)

        tasks = self.task_repository.list_all()
        calendar_events = self.calendar_event_repository.list_all()

        events_by_task = {}

        for event in calendar_events:
            if event.task_id is not None:
                events_by_task.setdefault(event.task_id, []).append(event)

        issues = []

        for task in tasks:
            task_events = events_by_task.get(task.id, [])

            # 1. Scheduled task without a calendar event
            if task.status == TaskStatus.SCHEDULED and not task_events:
                issues.append({
                    "type": "missing_calendar_event",
                    "task_id": task.id,
                    "title": task.title,
                    "message": "Task is scheduled but has no calendar event.",
                })

            # 2. Completed/cancelled/missed/postponed task
            #    still represented in the calendar
            if task.status in {
                TaskStatus.COMPLETED,
                TaskStatus.CANCELLED,
                TaskStatus.MISSED,
                TaskStatus.POSTPONED,
            } and task_events:
                issues.append({
                    "type": "stale_calendar_event",
                    "task_id": task.id,
                    "title": task.title,
                    "message": (
                        f"Task is '{task.status}' but still has "
                        f"{len(task_events)} calendar event(s)."
                    ),
                })

            # Nothing else can be determined without a scheduled
            # calendar event.
            for event in task_events:
                # 3. Scheduled task ended without being started
                if (
                    task.status == TaskStatus.SCHEDULED
                    and event.end_time < now
                    and task.actual_start is None
                ):
                    issues.append({
                        "type": "overdue_unstarted_task",
                        "task_id": task.id,
                        "calendar_event_id": event.id,
                        "title": task.title,
                        "message": (
                            "Scheduled time has passed and the task "
                            "was never started."
                        ),
                    })

                # 4. Task was started but its scheduled time has passed
                if (
                    task.status == TaskStatus.IN_PROGRESS
                    and event.end_time < now
                    and task.actual_start is not None
                    and task.actual_end is None
                ):
                    issues.append({
                        "type": "overdue_in_progress_task",
                        "task_id": task.id,
                        "calendar_event_id": event.id,
                        "title": task.title,
                        "message": (
                            "Scheduled time has passed but the task "
                            "is still in progress."
                        ),
                    })

        return issues
    
    def cleanup_stale_calendar_events(self) -> list[int]:
        removed_event_ids = []

        from app.services.calendar_service import CalendarService

        calendar_service = CalendarService(self.session)

        tasks = self.task_repository.list_all()

        for task in tasks:
            if task.status not in {
                TaskStatus.COMPLETED,
                TaskStatus.CANCELLED,
                TaskStatus.MISSED,
                TaskStatus.POSTPONED,
            }:
                continue

            events = self.calendar_event_repository.list_by_task(task.id)

            for event in events:
                calendar_service.remove_event(event.id)
                removed_event_ids.append(event.id)

        return removed_event_ids
    
    def evaluate(self) -> list[dict]:
        issues = self.inspect()
        actions = []

        for issue in issues:
            if issue["type"] == "stale_calendar_event":
                actions.append({
                    "type": "cleanup_calendar",
                    "task_id": issue["task_id"],
                    "requires_user": False,
                    "message": issue["message"],
                })

            elif issue["type"] == "overdue_unstarted_task":
                actions.append({
                    "type": "ask_user",
                    "task_id": issue["task_id"],
                    "calendar_event_id": issue["calendar_event_id"],
                    "requires_user": True,
                    "message": (
                        f"You didn't start '{issue['title']}'. "
                        "Do you want to reschedule it, mark it as missed, "
                        "or cancel it?"
                    ),
                })

            elif issue["type"] == "overdue_in_progress_task":
                actions.append({
                    "type": "ask_user",
                    "task_id": issue["task_id"],
                    "calendar_event_id": issue["calendar_event_id"],
                    "requires_user": True,
                    "message": (
                        f"'{issue['title']}' was started but is not completed. "
                        "Do you want to continue it, reschedule it, "
                        "or mark it as completed?"
                    ),
                })
        return actions
    
    
    # ------------------------------------------------------------------
    # Notifications (user-facing, non-blocking)
    # ------------------------------------------------------------------

    @staticmethod
    def _clock(dt: datetime) -> str:
        return dt.astimezone(LIFEOS_TIMEZONE).strftime("%H:%M")

    def list_notifications(self) -> list[dict]:
        """
        Derive the notifications the user should see RIGHT NOW from
        real database state. Nothing is stored: once the user resolves
        an item (or its state changes), it simply stops being reported.
        """

        now = datetime.now(LIFEOS_TIMEZONE)
        notifications = []

        for task in self.task_repository.list_all():
            if task.status not in {
                TaskStatus.SCHEDULED,
                TaskStatus.IN_PROGRESS,
            }:
                continue

            for event in self.calendar_event_repository.list_by_task(
                task.id
            ):
                window = (
                    f"{self._clock(event.start_time)}–"
                    f"{self._clock(event.end_time)}"
                )

                if (
                    task.status == TaskStatus.SCHEDULED
                    and task.actual_start is None
                    and event.start_time <= now < event.end_time
                ):
                    kind = "due_now"
                    message = (
                        f"It's time for '{task.title}' ({window}). "
                        "Have you started?"
                    )
                    actions = ["start", "reschedule", "cancelled"]

                elif (
                    task.status == TaskStatus.SCHEDULED
                    and task.actual_start is None
                    and event.end_time < now
                ):
                    kind = "overdue_unstarted"
                    message = (
                        f"'{task.title}' was scheduled for {window} "
                        "but was never started."
                    )
                    actions = [
                        "completed",
                        "missed",
                        "reschedule",
                        "cancelled",
                    ]

                elif (
                    task.status == TaskStatus.IN_PROGRESS
                    and task.actual_end is None
                    and event.end_time < now
                ):
                    kind = "overdue_in_progress"
                    message = (
                        f"'{task.title}' is still in progress past its "
                        f"scheduled end ({self._clock(event.end_time)})."
                    )
                    actions = ["completed", "reschedule", "cancelled"]

                else:
                    continue

                notifications.append({
                    "id": f"{kind}:{task.id}:{event.id}",
                    "type": kind,
                    "task_id": task.id,
                    "calendar_event_id": event.id,
                    "title": task.title,
                    "message": message,
                    "start_time": event.start_time.isoformat(),
                    "end_time": event.end_time.isoformat(),
                    "actions": actions,
                })

        notifications.sort(key=lambda n: n["end_time"])

        return notifications

    def apply_action(
        self,
        task_id: int,
        action: str,
    ) -> None:
        """
        Execute a notification quick action. Business rules stay in
        TaskService. The caller commits. 'reschedule' is NOT handled
        here: it needs a conversation, so the UI hands it to the chat.
        """

        from app.services.calendar_service import CalendarService
        from app.services.task_service import TaskService

        task_service = TaskService(self.session)
        calendar_service = CalendarService(self.session)

        task = task_service.get_task(task_id)

        if task is None:
            raise ValueError(f"Task #{task_id} not found.")

        if action == "start":
            task_service.start_task(task_id)
            return

        if action == "completed":
            if task.actual_start is not None and task.actual_end is None:
                task_service.complete_task(task_id)
            else:
                task_service.update_status_by_id(
                    task_id, TaskStatus.COMPLETED
                )

        elif action == "missed":
            task_service.update_status_by_id(task_id, TaskStatus.MISSED)

        elif action == "cancelled":
            task_service.update_status_by_id(task_id, TaskStatus.CANCELLED)

        else:
            raise ValueError(f"Unsupported action '{action}'.")

        # The task is resolved: its calendar events are now stale.
        for event in self.calendar_event_repository.list_by_task(task_id):
            calendar_service.remove_event(event.id)
    

