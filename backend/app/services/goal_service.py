from typing import Any

from sqlalchemy.orm import Session

from app.repositories.goals import GoalRepository
from app.repositories.tasks import TaskRepository


class GoalService:
    """
    Application-level service responsible for creating and
    managing goals together with their tasks.

    Agents should call this service rather than accessing
    repositories directly.
    """

    def __init__(self, session: Session):
        self.session = session
        self.goal_repository = GoalRepository(session)
        self.task_repository = TaskRepository(session)

    def create_goal_with_task(
        self,
        goal_name: str,
        task_description: str,
        estimated_duration_minutes: int,
        priority: str = "medium",
    ) -> dict[str, Any]:
        """
        Create a goal and its initial task in one transaction.

        The caller owns the transaction boundary.
        """

        goal = self.goal_repository.create(
            name=goal_name,
            priority=priority,
        )

        task = self.task_repository.create(
            goal_id=goal.id,
            title=task_description,
            estimated_duration_minutes=estimated_duration_minutes,
            priority=priority,
        )

        return {
            "goal": goal,
            "task": task,
        }