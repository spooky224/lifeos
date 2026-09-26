import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from app.db.session import SessionLocal
from app.graph.state import LifeOSState
from app.services.goal_service import GoalService

load_dotenv()


class GoalContext(BaseModel):
    goal_name: str = Field(
        description="The goal or project the user is referring to."
    )
    task_description: str = Field(
        description="The specific work the user wants to accomplish."
    )
    estimated_duration_minutes: int = Field(
        description="The requested or inferred duration in minutes."
    )
    priority: str = Field(
        description="Estimated priority: low, medium, or high."
    )


model = ChatGroq(
    model=os.getenv("LIFEOS_MODEL"),
    temperature=0,
)

goal_model = model.with_structured_output(GoalContext)


def goal_agent(state: LifeOSState) -> LifeOSState:
    user_request = state["user_request"]

    prompt = f"""
You are the Goal Agent of LIFEOS.

Your responsibility is to understand the goal or project
behind the user's request.

Analyze the request and identify:

1. The goal/project involved.
2. The specific task the user wants to accomplish.
3. The requested duration.
4. A reasonable priority.

Do not invent deadlines or facts that are not present.
If priority is not explicitly stated, infer a reasonable default.

User request:
{user_request}
"""

    result = goal_model.invoke(prompt)

    session = SessionLocal()

    try:
        goal_service = GoalService(session)

        persisted = goal_service.create_goal_with_task(
            goal_name=result.goal_name,
            task_description=result.task_description,
            estimated_duration_minutes=result.estimated_duration_minutes,
            priority=result.priority,
        )

        session.commit()

        goal = persisted["goal"]
        task = persisted["task"]

        return {
            "goal_context": {
                "goal_name": result.goal_name,
                "task_description": result.task_description,
                "estimated_duration_minutes": result.estimated_duration_minutes,
                "priority": result.priority,
                "goal_id": goal.id,
                "task_id": task.id,
            },
            "task_context": {
                "task_id": task.id,
                "title": task.title,
                "estimated_duration_minutes": task.estimated_duration_minutes,
                "priority": task.priority,
                "goal_id": goal.id,
            },
            "messages": state.get("messages", []) + [
                {
                    "role": "goal_agent",
                    "content": (
                        f"Identified goal: {result.goal_name}. "
                        f"Task: {result.task_description}. "
                        f"Persisted goal_id={goal.id}, task_id={task.id}."
                    ),
                }
            ],
        }

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()