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
            "Must be one of: conversation, goal, task_create, "
            "routine, calendar, task_update, other."
        )
    )

    reasoning: str = Field(
        description="Short explanation of why this intent was identified."
    )

    resolved_request: str = Field(
        default="",
        description=(
            "For an action intent, rewrite the CURRENT request as a self-contained "
            "instruction using relevant facts from recent conversation. Resolve "
            "references such as 'that' or 'it', preserve constraints, and do not add "
            "actions the user did not request. For conversation, repeat the current "
            "request unchanged."
        ),
    )


model = ChatGroq(
    model=os.getenv("LIFEOS_MODEL"),
    temperature=0,
)

intent_model = model.with_structured_output(UserIntent)


def personal_agent(state: LifeOSState) -> LifeOSState:
    user_request = state["user_request"]
    conversation_history = state.get("conversation_history", [])[-12:]

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
   - "Add another task to my AI project."
   - "What's left on my AI project?"
   - "Show me my goals."

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
   The user wants to modify an EXISTING task, including its properties
   or its lifecycle status.

   Property edits:
   - "Change its duration to 2 hours."
   - "Rename the task to Review LangGraph documentation."
   - "Set that task's priority to high."
   - "Change the description of my AI task."

   Status changes:
   - "I finished my AI project."
   - "I completed my workout."
   - "I missed my workout."
   - "I postponed my presentation."
   - "I'm working on my AI project."
   - "Cancel my AI project."

   Do not classify edits to an existing task's title, duration, priority,
   or description as calendar or conversation requests.

6. conversation
   The user is talking naturally, reflecting, sharing feelings,
   asking for advice or general information, greeting you, or
   continuing a discussion without asking LIFEOS to change data.

   Examples:
   - "Hey, how are you?"
   - "I'm tired and feel like I made no progress today."
   - "What do you think I should focus on?"
   - "Why is it so hard to stay consistent?"

7. other
   Use only when no intent fits confidently. Prefer conversation
   over other for normal human dialogue.

Important classification rules:
# LIFEOS_CONTEXT_INTENT_FIX_V1
CURRENT-REQUEST PRECEDENCE (CRITICAL):
- Classify the user's CURRENT message first. Use earlier conversation only to
  resolve references such as "that goal" or "the task we discussed"; never let
  the previous topic override a different project explicitly named now.
- A request like "I want to work on LIFEOS for two hours this week, preferably
  after 1 PM" is a one-time work task with scheduling constraints. Classify it
  as task_create (not goal, task_update, or a continuation of the previous goal).
- Do not attach a task to the previously discussed goal merely because that
  goal appears in conversation history. A task may be independent (goal_id=None).
  Link it to a goal only when the current request explicitly names that goal or
  clearly asks to add the task to it.
- Use goal only when the current message asks to create/define a larger goal,
  or explicitly asks to add work to a particular existing goal. For example,
  "Let's turn that into a goal" refers to the immediately preceding problem;
  it does not make every later work request part of that goal.
- If the current request names a different project, preserve that project in
  the task title and scheduling context. Do not reuse a previous goal/task title.


- Use CONVERSATION by default when the user is talking, thinking aloud,
  asking for advice, or sharing an experience rather than requesting a
  concrete change to LIFEOS data.
- A follow-up such as "let's turn that into a goal" is an action request;
  use the surrounding conversation to resolve what "that" refers to.
- Do not create goals, tasks, routines, or calendar events merely because
  the user discusses them. They must express an intention to act.
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

Recent conversation (oldest to newest):
{conversation_history}

Current user request:
{user_request}

Use the recent conversation to resolve references such as "it", "that",
"the project", or "let's do it". Classify the CURRENT request, not the
previous turn.
- For an action intent, set resolved_request to a self-contained version of
  the current action, carrying forward only relevant context and constraints.
  Do not turn discussion into action. For conversation intent, keep the
  current message unchanged in resolved_request.
- Return the structured intent only.
"""

    try:
        result = intent_model.invoke(prompt)
    except Exception:
        clarification = (
            "I didn't quite understand that. Could you rephrase it?"
        )
        return {
            "intent": "other",
            "topic_switch": False,
            "final_response": clarification,
            "messages": state.get("messages", []) + [
                {"role": "personal_agent", "content": clarification}
            ],
        }

    resolved_request = (result.resolved_request or "").strip()
    return {
        "intent": result.intent,
        # Downstream domain agents receive a self-contained request.
        # Original wording remains in conversation_history.
        "user_request": (
            resolved_request
            if result.intent not in ("conversation", "other") and resolved_request
            else user_request
        ),
        "topic_switch": False,
        "messages": state.get("messages", []) + [
            {
                "role": "personal_agent",
                "content": result.reasoning,
            }
        ],
    }