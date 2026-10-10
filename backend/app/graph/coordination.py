"""Deterministic coordination primitives for the LIFEOS graph."""
from typing import Any


def build_coordination_plan(intent: str | None) -> list[str]:
    """Describe the expected agent chain for a classified intent."""
    plans = {
        "goal": ["goal_agent", "calendar_agent_if_scheduling_requested"],
        "task_create": ["task_agent", "calendar_agent_if_scheduling_requested"],
        "task_update": ["task_agent"],
        "routine": ["routine_agent", "approval", "execute_calendar_action_if_approved"],
        "calendar": ["calendar_agent", "approval", "execute_calendar_action_if_approved"],
        "conversation": ["conversation_agent"],
        "other": ["conversation_agent"],
    }
    return list(plans.get(intent or "conversation", plans["conversation"]))


def make_handoff(source: str, target: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Build a compact structured handoff, omitting missing values."""
    return {
        "from_agent": source,
        "to_agent": target,
        "payload": {key: value for key, value in payload.items() if value is not None},
    }
