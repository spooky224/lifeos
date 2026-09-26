from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.routine import Routine
from app.repositories.routines import RoutineRepository
from app.repositories.tasks import TaskRepository


class RoutineService:
    """
    Application-level service responsible for turning recurring
    routines into concrete task instances.
    """

    def __init__(self, session: Session):
        self.session = session
        self.routine_repository = RoutineRepository(session)
        self.task_repository = TaskRepository(session)

    def should_run_on(
        self,
        routine: Routine,
        target_date: date,
    ) -> bool:
        """
        Determine whether a routine should generate a task
        for the given date.
        """

        if not routine.is_active:
            return False

        if routine.frequency == "daily":
            return True

        if routine.frequency == "weekly":
            if not routine.days_of_week:
                return False

            return target_date.weekday() in routine.days_of_week

        if routine.frequency == "monthly":
            if not routine.days_of_week:
                return False

            # For monthly routines, the first value represents
            # the day of the month (1-31).
            return target_date.day in routine.days_of_week

        return False

    def build_deadline(
        self,
        routine: Routine,
        target_date: date,
    ) -> datetime | None:
        """
        Build a timezone-naive deadline from the routine's
        preferred time.

        Timezone handling will be added when LIFEOS introduces
        user timezone preferences.
        """

        if routine.preferred_time is None:
            return None

        return datetime.combine(
            target_date,
            routine.preferred_time,
        )

    def generate_task(
        self,
        routine: Routine,
        target_date: date,
    ) -> dict[str, Any] | None:
        """
        Generate one task occurrence for a routine.

        Returns None when the routine should not run or when
        the occurrence already exists.
        """

        if not self.should_run_on(routine, target_date):
            return None

        existing_task = self.task_repository.get_routine_occurrence(
            routine_id=routine.id,
            routine_date=target_date,
        )

        if existing_task is not None:
            return {
                "created": False,
                "reason": "already_exists",
                "task": existing_task,
            }

        task = self.task_repository.create(
            goal_id=routine.goal_id,
            routine_id=routine.id,
            routine_date=target_date,
            title=routine.name,
            description=routine.description,
            estimated_duration_minutes=routine.duration_minutes,
            priority=routine.priority,
            deadline=self.build_deadline(
                routine,
                target_date,
            ),
        )

        return {
            "created": True,
            "reason": "created",
            "task": task,
        }

    def generate_for_date(
        self,
        target_date: date,
    ) -> list[dict[str, Any]]:
        """
        Generate all applicable routine tasks for a date.
        """

        routines = self.routine_repository.list_active()

        results = []

        for routine in routines:
            result = self.generate_task(
                routine=routine,
                target_date=target_date,
            )

            if result is not None:
                results.append(
                    {
                        "routine_id": routine.id,
                        "routine_name": routine.name,
                        **result,
                    }
                )

        return results

    def generate_for_date_and_commit(
        self,
        target_date: date,
    ) -> list[dict[str, Any]]:
        """
        Generate routine tasks and commit them as one transaction.
        """

        results = self.generate_for_date(target_date)

        self.session.commit()

        return results
