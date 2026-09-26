import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from app.graph.state import LifeOSState

load_dotenv()


class UserIntent(BaseModel):
    intent: str = Field(
        description=(
            "Main intent of the request. "
            "Must be one of: goal, task_create, routine, "
            "calendar, task_update, other."
        )
    )

    reasoning: str = Field(
        description="Short explanation of why this intent was identified."
    )


model = ChatGroq(
    model=os.getenv("LIFEOS_MODEL"),
    temperature=0,
)

intent_model = model.with_structured_output(UserIntent)


def personal_agent(state: LifeOSState) -> LifeOSState:
    user_request = state["user_request"]

    prompt = f"""
You are the Personal Agent of LIFEOS.

Your responsibility is to understand the user's request
and identify which specialized LIFEOS agent should handle it.

Available intents:

1. goal
   The user wants to create, define, or work on a larger
   objective that may contain multiple tasks or routines.

   Examples:
   - "I want to gain 10kg next month."
   - "I want to prepare for my AI certification."
   - "Create a goal to improve my fitness."

2. task_create
   The user wants to create a new one-time task.
   The task may optionally be scheduled immediately.

   Examples:
   - "I need to buy groceries tomorrow."
   - "Create a task to prepare my presentation."
   - "Schedule a task to go to the supermarket tomorrow at 10am."
   - "I need to study Python for 2 hours tomorrow."

3. routine
   The user wants to create, change, activate, deactivate,
   or otherwise manage a recurring routine.

   Examples:
   - "I want to read 30 minutes every evening."
   - "Create a routine to go to the gym every Monday."
   - "Set my prayers as a daily routine."

4. calendar
   The user is asking about calendar availability
   or wants to schedule/reschedule an EXISTING task.

   Examples:
   - "When am I free tomorrow?"
   - "Schedule my AI presentation task tomorrow."
   - "Move my grocery task to Friday at 10am."

5. task_update
   The user wants to update the status of an existing task.

   Examples:
   - "I finished my AI project."
   - "I completed my workout."
   - "I missed my workout."
   - "I postponed my presentation."
   - "I'm working on my AI project."

6. other
   The request does not currently belong to one of
   the specialized agents.

Important classification rules:

- A recurring activity is a ROUTINE request.
- A one-time activity is a TASK_CREATE request.
- A larger objective involving multiple activities is a GOAL request.
- Scheduling an EXISTING task is a CALENDAR request.
- Updating the status of an EXISTING task is a TASK_UPDATE request.
- Do not classify a new one-time task as a GOAL simply because
  the task mentions a project or activity.
- If the user asks to create a task and schedule it immediately,
  classify it as TASK_CREATE.
- If the user refers to a task that already exists and asks
  when or where it should be scheduled, classify it as CALENDAR.

User request:
{user_request}

Return the structured intent only.
"""

    result = intent_model.invoke(prompt)

    return {
        "intent": result.intent,
        "messages": state.get("messages", []) + [
            {
                "role": "personal_agent",
                "content": result.reasoning,
            }
        ],
    }