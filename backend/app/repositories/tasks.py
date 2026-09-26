from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.task import Task, TaskStatus


class TaskRepository:
    """
    Database access layer for Task entities.
    """

    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        goal_id: int | None,
        title: str,
        estimated_duration_minutes: int,
        description: str | None = None,
        priority: str = "medium",
        deadline: datetime | None = None,
        routine_id: int | None = None,
        routine_date: date | None = None,
    ) -> Task:
        task = Task(
            goal_id=goal_id,
            routine_id=routine_id,
            routine_date=routine_date,
            title=title,
            description=description,
            estimated_duration_minutes=estimated_duration_minutes,
            priority=priority,
            status=TaskStatus.PLANNED,
            deadline=deadline,
        )

        self.session.add(task)
        self.session.flush()

        return task

    def get_by_id(self, task_id: int) -> Task | None:
        statement = select(Task).where(Task.id == task_id)
        return self.session.scalar(statement)

    def list_by_goal(self, goal_id: int) -> list[Task]:
        statement = (
            select(Task)
            .where(Task.goal_id == goal_id)
            .order_by(Task.created_at.desc())
        )

        return list(self.session.scalars(statement).all())

    def list_by_routine(self, routine_id: int) -> list[Task]:
        statement = (
            select(Task)
            .where(Task.routine_id == routine_id)
            .order_by(Task.routine_date.desc().nulls_last())
        )

        return list(self.session.scalars(statement).all())

    def get_routine_occurrence(
        self,
        routine_id: int,
        routine_date: date,
    ) -> Task | None:
        statement = (
            select(Task)
            .where(
                Task.routine_id == routine_id,
                Task.routine_date == routine_date,
            )
        )

        return self.session.scalar(statement)

    def list_by_status(
        self,
        status: TaskStatus,
    ) -> list[Task]:
        statement = (
            select(Task)
            .where(Task.status == status)
            .order_by(Task.deadline.asc().nulls_last())
        )

        return list(self.session.scalars(statement).all())

    def update_status(
        self,
        task: Task,
        status: TaskStatus,
    ) -> Task:
        task.status = status
        self.session.flush()

        return task

    def update_deadline(
        self,
        task: Task,
        deadline: datetime | None,
    ) -> Task:
        task.deadline = deadline
        self.session.flush()

        return task

    def delete(self, task: Task) -> None:
        self.session.delete(task)
        self.session.flush()

    def list_all(self) -> list[Task]:
        statement = select(Task).order_by(Task.created_at.desc())
        return list(self.session.scalars(statement).all())
