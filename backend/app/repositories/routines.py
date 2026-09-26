from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.routine import Routine


class RoutineRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        name: str,
        frequency: str,
        duration_minutes: int,
        goal_id: int | None = None,
        description: str | None = None,
        days_of_week: list[int] | None = None,
        preferred_time=None,
        priority: str = "medium",
    ) -> Routine:
        routine = Routine(
            name=name,
            description=description,
            frequency=frequency,
            days_of_week=days_of_week,
            preferred_time=preferred_time,
            duration_minutes=duration_minutes,
            priority=priority,
            goal_id=goal_id,
            is_active=True,
        )

        self.session.add(routine)
        self.session.flush()

        return routine

    def get_by_id(self, routine_id: int) -> Routine | None:
        statement = select(Routine).where(Routine.id == routine_id)
        return self.session.scalar(statement)

    def list_all(self) -> list[Routine]:
        statement = select(Routine).order_by(Routine.created_at.desc())
        return list(self.session.scalars(statement).all())

    def list_active(self) -> list[Routine]:
        statement = (
            select(Routine)
            .where(Routine.is_active.is_(True))
            .order_by(Routine.created_at.desc())
        )

        return list(self.session.scalars(statement).all())

    def deactivate(self, routine: Routine) -> Routine:
        routine.is_active = False
        self.session.flush()
        return routine

    def activate(self, routine: Routine) -> Routine:
        routine.is_active = True
        self.session.flush()
        return routine

    def delete(self, routine: Routine) -> None:
        self.session.delete(routine)
        self.session.flush()
