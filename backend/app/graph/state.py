from typing import Any, TypedDict


class LifeOSState(TypedDict, total=False):
    # Conversation
    user_request: str
    messages: list[dict[str, Any]]

    # Understanding
    intent: str

    # Domain contexts
    task_context: dict[str, Any]
    goal_context: dict[str, Any]
    routine_context: dict[str, Any]

    # Calendar / planning
    calendar_context: dict[str, Any]
    proposed_actions: list[dict[str, Any]]

    # Human-in-the-loop
    pending_approval: bool
    approval_message: str
    approval_decision: str

    # Execution
    execution_results: list[dict[str, Any]]
    
    # Lifecycle
    lifecycle_issues: list[dict[str, Any]]
    lifecycle_actions: list[dict[str, Any]]
    pending_reschedule: dict[str, Any]

    # Final response
    final_response: str
    
    schedule_requested: bool