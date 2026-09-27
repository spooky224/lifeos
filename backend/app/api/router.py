from datetime import date, datetime, timedelta, time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.db.session import SessionLocal
from app.repositories.tasks import TaskRepository
from app.db.session import SessionLocal
from app.graph.workflow import build_graph
from app.models.task import TaskStatus
from app.repositories.calendar_events import CalendarEventRepository
from app.repositories.goals import GoalRepository
from app.repositories.tasks import TaskRepository
from app.services.routine_service import RoutineService
from app.services.task_service import TaskService
from app.models.routine import Routine
from app.repositories.routines import RoutineRepository
router = APIRouter()
graph = build_graph()


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "lifeos-api"


class ApprovalRequest(BaseModel):
    decision: str


class ResumeRequest(BaseModel):
    answer: str


class TaskStatusRequest(BaseModel):
    status: TaskStatus

class RoutineCreateRequest(BaseModel):
    name: str
    frequency: str
    duration_minutes: int
    goal_id: int | None = None
    description: str | None = None
    days_of_week: list[int] | None = None
    preferred_time: str | None = None
    priority: str = "medium"


@router.post("/routines")
def create_routine(request: RoutineCreateRequest):
    session = SessionLocal()

    try:
        preferred_time = None

        if request.preferred_time:
            try:
                preferred_time = time.fromisoformat(
                    request.preferred_time
                )
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="preferred_time must use HH:MM format.",
                )

        if request.duration_minutes <= 0:
            raise HTTPException(
                status_code=400,
                detail="duration_minutes must be greater than 0.",
            )

        if request.frequency not in {
            "daily",
            "weekly",
            "monthly",
        }:
            raise HTTPException(
                status_code=400,
                detail="frequency must be daily, weekly, or monthly.",
            )

        if request.days_of_week:
            invalid_days = [
                day
                for day in request.days_of_week
                if day < 0 or day > 6
            ]

            if invalid_days:
                raise HTTPException(
                    status_code=400,
                    detail="days_of_week must contain values from 0 to 6.",
                )

        repository = RoutineRepository(session)

        routine = repository.create(
            name=request.name,
            frequency=request.frequency,
            duration_minutes=request.duration_minutes,
            goal_id=request.goal_id,
            description=request.description,
            days_of_week=request.days_of_week,
            preferred_time=preferred_time,
            priority=request.priority,
        )

        session.commit()

        return {
            "id": routine.id,
            "goal_id": routine.goal_id,
            "name": routine.name,
            "description": routine.description,
            "frequency": routine.frequency,
            "days_of_week": routine.days_of_week,
            "preferred_time": (
                routine.preferred_time.isoformat()
                if routine.preferred_time
                else None
            ),
            "duration_minutes": routine.duration_minutes,
            "priority": routine.priority,
            "is_active": routine.is_active,
            "created_at": routine.created_at,
            "updated_at": routine.updated_at,
        }

    except HTTPException:
        session.rollback()
        raise

    except Exception as exc:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    finally:
        session.close()


@router.get("/routines")
def get_routines():
    session = SessionLocal()

    try:
        repository = RoutineRepository(session)

        routines = repository.list_all()

        return [
            {
                "id": routine.id,
                "goal_id": routine.goal_id,
                "name": routine.name,
                "description": routine.description,
                "frequency": routine.frequency,
                "days_of_week": routine.days_of_week,
                "preferred_time": (
                    routine.preferred_time.isoformat()
                    if routine.preferred_time
                    else None
                ),
                "duration_minutes": routine.duration_minutes,
                "priority": routine.priority,
                "is_active": routine.is_active,
                "created_at": routine.created_at,
                "updated_at": routine.updated_at,
            }
            for routine in routines
        ]

    finally:
        session.close()


@router.patch("/routines/{routine_id}/activate")
def activate_routine(routine_id: int):
    session = SessionLocal()

    try:
        repository = RoutineRepository(session)

        routine = repository.get_by_id(routine_id)

        if routine is None:
            raise HTTPException(
                status_code=404,
                detail=f"Routine {routine_id} not found.",
            )

        repository.activate(routine)

        session.commit()

        return {
            "id": routine.id,
            "is_active": routine.is_active,
        }

    except HTTPException:
        session.rollback()
        raise

    except Exception as exc:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    finally:
        session.close()


@router.patch("/routines/{routine_id}/deactivate")
def deactivate_routine(routine_id: int):
    session = SessionLocal()

    try:
        repository = RoutineRepository(session)

        routine = repository.get_by_id(routine_id)

        if routine is None:
            raise HTTPException(
                status_code=404,
                detail=f"Routine {routine_id} not found.",
            )

        repository.deactivate(routine)

        session.commit()

        return {
            "id": routine.id,
            "is_active": routine.is_active,
        }

    except HTTPException:
        session.rollback()
        raise

    except Exception as exc:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    finally:
        session.close()


@router.delete("/routines/{routine_id}")
def delete_routine(routine_id: int):
    session = SessionLocal()

    try:
        repository = RoutineRepository(session)

        routine = repository.get_by_id(routine_id)

        if routine is None:
            raise HTTPException(
                status_code=404,
                detail=f"Routine {routine_id} not found.",
            )

        repository.delete(routine)

        session.commit()

        return {
            "status": "deleted",
            "id": routine_id,
        }

    except HTTPException:
        session.rollback()
        raise

    except Exception as exc:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    finally:
        session.close()
@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "LIFEOS",
    }


@router.post("/chat")
def chat(request: ChatRequest):

    config = {
        "configurable": {
            "thread_id": request.thread_id,
        }
    }

    try:
        current_state = graph.get_state(config)
        state_values = current_state.values

        input_state = {
            "user_request": request.message,
        }

        pending_reschedule = state_values.get("pending_reschedule")

        if pending_reschedule:
            input_state["pending_reschedule"] = pending_reschedule

            session = SessionLocal()

            try:
                task_repository = TaskRepository(session)

                task = task_repository.get_by_id(
                    pending_reschedule["task_id"]
                )

                if task is None:
                    raise ValueError(
                        f"Task #{pending_reschedule['task_id']} not found."
                    )

                input_state["task_context"] = {
                    "task_id": task.id,
                    "title": task.title,
                    "description": task.description,
                    "estimated_duration_minutes": (
                        task.estimated_duration_minutes
                    ),
                }

            finally:
                session.close()

        result = graph.invoke(
            input_state,
            config,
        )

        if "__interrupt__" in result:
            interrupt_data = result["__interrupt__"][0]

            return {
                "status": "approval_required",
                "message": interrupt_data.value,
                "thread_id": request.thread_id,
            }

        return {
            "status": "completed",
            "result": result,
            "thread_id": request.thread_id,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

@router.get("/goals")
def get_goals():
    session = SessionLocal()

    try:
        repository = GoalRepository(session)
        goals = repository.list_all()

        return [
            {
                "id": goal.id,
                "name": goal.name,
                "priority": goal.priority,
                "status": goal.status,
                "created_at": goal.created_at,
            }
            for goal in goals
        ]

    finally:
        session.close()


@router.get("/tasks")
def get_tasks():
    session = SessionLocal()

    try:
        repository = TaskRepository(session)
        tasks = repository.list_all()

        return [
            {
                "id": task.id,
                "goal_id": task.goal_id,
                "title": task.title,
                "description": task.description,
                "estimated_duration_minutes": task.estimated_duration_minutes,
                "priority": task.priority,
                "status": task.status,
                "deadline": task.deadline,
            }
            for task in tasks
        ]

    finally:
        session.close()


@router.post("/tasks/{task_id}/start")
def start_task(task_id: int):
    session = SessionLocal()

    try:
        task_service = TaskService(session)

        task = task_service.start_task(task_id)

        session.commit()
        session.refresh(task)

        return {
            "status": "started",
            "task": {
                "id": task.id,
                "title": task.title,
                "status": (
                    task.status.value
                    if hasattr(task.status, "value")
                    else task.status
                ),
                "actual_start": (
                    task.actual_start.isoformat()
                    if task.actual_start
                    else None
                ),
            },
        }

    except ValueError as exc:
        session.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    finally:
        session.close()


@router.post("/tasks/{task_id}/complete")
def complete_task(task_id: int):
    session = SessionLocal()

    try:
        task_service = TaskService(session)

        task = task_service.complete_task(task_id)

        session.commit()
        session.refresh(task)

        return {
            "status": "completed",
            "task": {
                "id": task.id,
                "title": task.title,
                "status": (
                    task.status.value
                    if hasattr(task.status, "value")
                    else task.status
                ),
                "actual_start": (
                    task.actual_start.isoformat()
                    if task.actual_start
                    else None
                ),
                "actual_end": (
                    task.actual_end.isoformat()
                    if task.actual_end
                    else None
                ),
                "actual_duration_minutes": (
                    task.actual_duration_minutes
                ),
                "estimated_duration_minutes": (
                    task.estimated_duration_minutes
                ),
            },
        }

    except ValueError as exc:
        session.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    finally:
        session.close()
        
@router.patch("/tasks/{task_id}/status")
def update_task_status(
    task_id: int,
    request: TaskStatusRequest,
):
    session = SessionLocal()

    try:
        service = TaskService(session)

        task = service.get_task(task_id)

        if task is None:
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} not found.",
            )

        try:
            task = service.update_status(
                task,
                request.status,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            )

        session.commit()

        return {
            "id": task.id,
            "status": task.status,
        }

    except HTTPException:
        session.rollback()
        raise

    except Exception as exc:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    finally:
        session.close()
@router.get("/calendar")
def get_calendar():
    session = SessionLocal()

    try:
        repository = CalendarEventRepository(session)

        now = datetime.now().astimezone()
        end = now + timedelta(days=30)

        events = repository.list_between(
            start_time=now,
            end_time=end,
        )

        return [
            {
                "id": event.id,
                "task_id": event.task_id,
                "google_event_id": event.google_event_id,
                "title": event.title,
                "start_time": event.start_time,
                "end_time": event.end_time,
                "status": event.status,
            }
            for event in events
        ]

    finally:
        session.close()


@router.post("/approvals/{thread_id}")
def approve_action(
    thread_id: str,
    request: ApprovalRequest,
):
    decision = request.decision.lower().strip()

    allowed_decisions = {
        "approved",
        "rejected",
        "reschedule",
        "missed",
        "cancel",
    }

    if decision not in allowed_decisions:
        raise HTTPException(
            status_code=400,
            detail=(
                "Decision must be one of: "
                "approved, rejected, reschedule, missed, cancel."
            ),
        )

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    try:
        from langgraph.types import Command

        result = graph.invoke(
            Command(resume=decision),
            config,
        )

        return {
            "status": "completed",
            "thread_id": thread_id,
            "result": result,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )
        
@router.post("/chat/resume/{thread_id}")
def resume_chat(thread_id: str, request: ResumeRequest):
    """
    Resume a paused graph run (any interrupt() — task clarification,
    not just calendar approval) with a free-text answer.
    """

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    try:
        from langgraph.types import Command

        result = graph.invoke(
            Command(resume=request.answer),
            config,
        )

        if "__interrupt__" in result:
            interrupt_data = result["__interrupt__"][0]

            return {
                "status": "approval_required",
                "message": interrupt_data.value,
                "thread_id": thread_id,
            }

        return {
            "status": "completed",
            "result": result,
            "thread_id": thread_id,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


@router.post("/routines/generate")
def generate_routine_tasks(target_date: date | None = None):
    session = SessionLocal()

    try:
        target_date = target_date or date.today()

        service = RoutineService(session)
        result = service.generate_for_date_and_commit(target_date)

        generated = sum(1 for item in result if item["created"])
        skipped = sum(1 for item in result if not item["created"])

        return {
            "date": target_date,
            "generated": generated,
            "skipped": skipped,
            "results": [
                {
                    "routine_id": item["routine_id"],
                    "routine_name": item["routine_name"],
                    "created": item["created"],
                    "reason": item["reason"],
                    "task_id": (
                        item["task"].id
                        if item["task"] is not None
                        else None
                    ),
                }
                for item in result
            ],
        }

    except Exception as exc:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    finally:
        session.close()