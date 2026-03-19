"""Tests for models.py — Ticket, GoalAncestry, BudgetPolicy, OrgNode, Handoff."""
import time
import pytest
from agent_swarm.models import (
    GoalAncestry, BudgetPolicy, OrgNode, OrgRole,
    HeartbeatConfig, Ticket, Handoff,
)


# ── GoalAncestry ──

def test_goal_ancestry_full_chain():
    ga = GoalAncestry(mission="M", objective="O", task_goal="T")
    assert ga.chain() == "M → O → T"


def test_goal_ancestry_partial():
    ga = GoalAncestry(mission="M", task_goal="T")
    assert ga.chain() == "M → T"


def test_goal_ancestry_empty():
    ga = GoalAncestry()
    assert ga.chain() == ""


def test_goal_ancestry_mission_only():
    ga = GoalAncestry(mission="M")
    assert ga.chain() == "M"


# ── BudgetPolicy ──

def test_budget_policy_defaults():
    bp = BudgetPolicy()
    assert bp.max_cost_per_run == 0.0
    assert bp.warn_at_percent == 80.0
    assert bp.block_on_exceed is True
    assert bp.estimated_cost_per_call == 0.003


def test_budget_policy_custom():
    bp = BudgetPolicy(max_cost_per_run=10.0, max_cost_per_role={"lead": 5.0})
    assert bp.max_cost_per_run == 10.0
    assert bp.max_cost_per_role["lead"] == 5.0


# ── OrgNode ──

def test_org_node():
    node = OrgNode(role=OrgRole.MANAGER, agent_role="lead", reports_to="owner")
    assert node.role == OrgRole.MANAGER
    assert node.agent_role == "lead"
    assert node.reports_to == "owner"
    assert node.can_delegate_to == []


# ── HeartbeatConfig ──

def test_heartbeat_config_defaults():
    hc = HeartbeatConfig()
    assert hc.interval_seconds == 3600.0
    assert hc.check_pending_approvals is True
    assert hc.max_retries_per_heartbeat == 3


# ── Ticket ──

def test_ticket_auto_id():
    t = Ticket(title="Test ticket")
    assert len(t.ticket_id) == 8
    assert t.created_at > 0


def test_ticket_preserves_given_id():
    t = Ticket(ticket_id="custom123", title="Test")
    assert t.ticket_id == "custom123"


def test_ticket_to_dict():
    ga = GoalAncestry(mission="M", objective="O")
    t = Ticket(title="Fix bug", goal_ancestry=ga, priority="high")
    d = t.to_dict()
    assert d["title"] == "Fix bug"
    assert d["priority"] == "high"
    assert d["goal_chain"] == "M → O"
    assert "goal_ancestry" not in d


def test_ticket_to_dict_no_ancestry():
    t = Ticket(title="Simple")
    d = t.to_dict()
    assert d["goal_chain"] == ""


def test_ticket_defaults():
    t = Ticket()
    assert t.priority == "medium"
    assert t.status == "open"
    assert t.tags == []


# ── Handoff ──

def test_handoff_validate_no_schema():
    h = Handoff(from_agent="a", to_agent="b", payload={"x": 1})
    ok, msg = h.validate_payload()
    assert ok is True
    assert msg == "OK"


def test_handoff_validate_valid():
    h = Handoff(
        from_agent="a", to_agent="b",
        payload={"name": "test", "count": 5},
        payload_schema={"name": {"type": "str"}, "count": {"type": "int"}},
    )
    ok, msg = h.validate_payload()
    assert ok is True


def test_handoff_validate_missing_required():
    h = Handoff(
        from_agent="a", to_agent="b",
        payload={},
        payload_schema={"name": {"type": "str", "required": True}},
    )
    ok, msg = h.validate_payload()
    assert ok is False
    assert "missing" in msg.lower()


def test_handoff_validate_wrong_type():
    h = Handoff(
        from_agent="a", to_agent="b",
        payload={"count": "not_a_number"},
        payload_schema={"count": {"type": "int"}},
    )
    ok, msg = h.validate_payload()
    assert ok is False
    assert "expected int" in msg.lower()


def test_handoff_validate_optional_missing():
    h = Handoff(
        from_agent="a", to_agent="b",
        payload={},
        payload_schema={"note": {"type": "str", "required": False}},
    )
    ok, msg = h.validate_payload()
    assert ok is True


def test_handoff_to_context_str():
    h = Handoff(from_agent="researcher", to_agent="writer",
                payload={"summary": "key findings"}, reason="analysis complete")
    s = h.to_context_str()
    assert "[Handoff from researcher]" in s
    assert "analysis complete" in s
    assert "key findings" in s


def test_handoff_to_context_str_minimal():
    h = Handoff(from_agent="a", to_agent="b")
    s = h.to_context_str()
    assert "[Handoff from a]" in s
