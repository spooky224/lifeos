from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.task import Task, TaskStatus
from app.repositories.tasks import TaskRepository


class TaskService:
    """
    Domain service for task operations.

    Agents and API routes should use this service
    instead of implementing task business rules themselves.
    """

    ALLOWED_TRANSITIONS = {
        TaskStatus.PLANNED: {
            TaskStatus.SCHEDULED,
            TaskStatus.IN_PROGRESS,
            TaskStatus.CANCELLED,
        },
        TaskStatus.SCHEDULED: {
            TaskStatus.IN_PROGRESS,
            TaskStatus.POSTPONED,
            TaskStatus.MISSED,
            TaskStatus.CANCELLED,
            TaskStatus.COMPLETED,
        },
        TaskStatus.IN_PROGRESS: {
            TaskStatus.COMPLETED,
            TaskStatus.POSTPONED,
            TaskStatus.CANCELLED,
        },
        TaskStatus.POSTPONED: {
            TaskStatus.SCHEDULED,
            TaskStatus.CANCELLED,
        },
        TaskStatus.MISSED: {
            TaskStatus.SCHEDULED,
            TaskStatus.CANCELLED,
        },
        TaskStatus.COMPLETED: set(),
        TaskStatus.CANCELLED: set(),
    }

    def __init__(self, session: Session):
        self.session = session
        self.task_repository = TaskRepository(session)

    def get_task(self, task_id: int) -> Task | None:
        return self.task_repository.get_by_id(task_id)

    def list_tasks(self) -> list[Task]:
        return self.task_repository.list_all()

    def update_status(
        self,
        task: Task,
        new_status: TaskStatus,
    ) -> Task:
        current_status = task.status

        allowed_statuses = self.ALLOWED_TRANSITIONS.get(
            current_status,
            set(),
        )

        if new_status not in allowed_statuses:
            raise ValueError(
                f"Cannot change task #{task.id} "
                f"from '{current_status}' "
                f"to '{new_status}'."
            )

        return self.task_repository.update_status(
            task,
            new_status,
        )

    def update_status_by_id(
        self,
        task_id: int,
        new_status: TaskStatus,
    ) -> Task:
        task = self.get_task(task_id)

        if task is None:
            raise ValueError(
                f"Task #{task_id} not found."
            )

        return self.update_status(
            task,
            new_status,
        )

    def start_task(self, task_id: int) -> Task:
        """
        Start a scheduled task.

        The backend records the actual start timestamp.
        The LLM never supplies this timestamp.
        """

        task = self.get_task(task_id)

        if task is None:
            raise ValueError(
                f"Task #{task_id} not found."
            )

        if task.actual_start is not None:
            raise ValueError(
                f"Task #{task_id} has already been started."
            )

        self.update_status(
            task,
            TaskStatus.IN_PROGRESS,
        )

        task.actual_start = datetime.now(timezone.utc)

        self.session.flush()

        return task

    def complete_task(self, task_id: int) -> Task:
        """
        Complete an in-progress task.

        The backend records the actual end timestamp and
        calculates the real execution duration.
        """

        task = self.get_task(task_id)

        if task is None:
            raise ValueError(
                f"Task #{task_id} not found."
            )

        if task.actual_start is None:
            raise ValueError(
                f"Task #{task_id} cannot be completed "
                "because it has not been started."
            )

        if task.actual_end is not None:
            raise ValueError(
                f"Task #{task_id} has already been completed."
            )

        actual_end = datetime.now(timezone.utc)

        actual_duration_seconds = (
            actual_end - task.actual_start
        ).total_seconds()

        actual_duration_minutes = max(
            1,
            round(actual_duration_seconds / 60),
        )

        task.actual_end = actual_end
        task.actual_duration_minutes = actual_duration_minutes

        self.update_status(
            task,
            TaskStatus.COMPLETED,
        )

        self.session.flush()

        return task
    
    def create_task(
        self,
        title: str,
        estimated_duration_minutes: int,
        goal_id: int | None = None,
        description: str | None = None,
        priority: str = "medium",
        deadline: datetime | None = None,
        routine_id: int | None = None,
        routine_date=None,
    ) -> Task:
        return self.task_repository.create(
            goal_id=goal_id,
            title=title,
            estimated_duration_minutes=estimated_duration_minutes,
            description=description,
            priority=priority,
            deadline=deadline,
            routine_id=routine_id,
            routine_date=routine_date,
        )