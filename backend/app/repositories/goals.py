from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.goal import Goal, GoalStatus


class GoalRepository:
    """
    Database access layer for Goal entities.

    Agents and tools should use this repository instead of
    interacting directly with SQLAlchemy queries.
    """

    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        name: str,
        description: str | None = None,
        priority: str = "medium",
    ) -> Goal:
        goal = Goal(
            name=name,
            description=description,
            priority=priority,
            status=GoalStatus.ACTIVE,
        )

        self.session.add(goal)
        self.session.flush()

        return goal

    def get_by_id(self, goal_id: int) -> Goal | None:
        statement = select(Goal).where(Goal.id == goal_id)
        return self.session.scalar(statement)

    def list_active(self) -> list[Goal]:
        statement = (
            select(Goal)
            .where(Goal.status == GoalStatus.ACTIVE)
            .order_by(Goal.created_at.desc())
        )

        return list(self.session.scalars(statement).all())

    def update_status(
        self,
        goal: Goal,
        status: GoalStatus,
    ) -> Goal:
        goal.status = status
        self.session.flush()

        return goal

    def delete(self, goal: Goal) -> None:
        self.session.delete(goal)
        self.session.flush()

    def list_all(self) -> list[Goal]:
        statement = select(Goal).order_by(Goal.created_at.desc())
        return list(self.session.scalars(statement).all())
