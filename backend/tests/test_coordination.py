from app.graph.coordination import build_coordination_plan, make_handoff


def test_goal_workflow_can_handoff_to_calendar():
    assert build_coordination_plan("goal") == ["goal_agent", "calendar_agent_if_scheduling_requested"]


def test_task_creation_workflow_can_handoff_to_calendar():
    assert build_coordination_plan("task_create") == ["task_agent", "calendar_agent_if_scheduling_requested"]


def test_task_update_does_not_plan_calendar_mutation():
    assert build_coordination_plan("task_update") == ["task_agent"]


def test_routine_keeps_approval_before_execution():
    assert build_coordination_plan("routine") == ["routine_agent", "approval", "execute_calendar_action_if_approved"]


def test_unknown_intent_falls_back_to_conversation():
    assert build_coordination_plan("unexpected") == ["conversation_agent"]


def test_handoff_envelope_omits_missing_values():
    assert make_handoff("goal_agent", "calendar_agent", {"task_id": 42, "goal_id": None}) == {
        "from_agent": "goal_agent", "to_agent": "calendar_agent", "payload": {"task_id": 42}
    }
