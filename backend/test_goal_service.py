from app.db.session import SessionLocal
from app.services.goal_service import GoalService


def main() -> None:
    session = SessionLocal()

    try:
        service = GoalService(session)

        result = service.create_goal_with_task(
            goal_name="LIFEOS Service Test",
            task_description="Test application service persistence",
            estimated_duration_minutes=60,
            priority="high",
        )

        session.commit()

        goal = result["goal"]
        task = result["task"]

        print("=== GOAL SERVICE TEST ===")
        print(f"Goal created: id={goal.id}, name={goal.name}")
        print(f"Task created: id={task.id}, title={task.title}")
        print(f"Task goal_id: {task.goal_id}")
        print(f"Same goal: {task.goal_id == goal.id}")
        print()
        print("=== GOAL SERVICE TEST PASSED ===")

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


if __name__ == "__main__":
    main()