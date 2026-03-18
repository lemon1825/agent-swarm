"""Operational data models — Ticket, GoalAncestry, BudgetPolicy, OrgNode, Handoff."""
from __future__ import annotations
import json, time, uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

class OrgRole(str, Enum):
    OWNER = "owner"; MANAGER = "manager"; CONTRIBUTOR = "contributor"
    REVIEWER = "reviewer"; APPROVER = "approver"

@dataclass
class GoalAncestry:
    """Every task traces back to mission."""
    mission: str = ""; objective: str = ""; task_goal: str = ""
    def chain(self) -> str:
        parts = [p for p in (self.mission, self.objective, self.task_goal) if p]
        return " → ".join(parts) if parts else ""

@dataclass
class BudgetPolicy:
    max_cost_per_run: float = 0.0
    max_cost_per_role: Dict[str, float] = field(default_factory=dict)
    max_monthly_workspace: float = 0.0
    warn_at_percent: float = 80.0
    block_on_exceed: bool = True
    estimated_cost_per_call: float = 0.003  # Fallback when LLM doesn't report usage ($0.003 ≈ GPT-4o-mini avg)

@dataclass
class OrgNode:
    role: OrgRole; agent_role: str; reports_to: str = ""
    can_delegate_to: List[str] = field(default_factory=list)
    can_handoff_to: List[str] = field(default_factory=list)
    budget_limit: float = 0.0

@dataclass
class HeartbeatConfig:
    interval_seconds: float = 3600.0
    check_pending_approvals: bool = True
    check_failed_retries: bool = True
    generate_status_report: bool = False
    max_retries_per_heartbeat: int = 3

@dataclass
class Ticket:
    ticket_id: str = ""; title: str = ""; priority: str = "medium"
    assignee: str = ""; status: str = "open"
    goal_ancestry: Optional[GoalAncestry] = None
    estimated_cost: float = 0.0; actual_cost: float = 0.0
    parent_ticket: str = ""; tags: List[str] = field(default_factory=list)
    created_at: float = 0.0; updated_at: float = 0.0
    def __post_init__(self):
        if not self.ticket_id: self.ticket_id = uuid.uuid4().hex[:8]
        if not self.created_at: self.created_at = time.time()
    def to_dict(self) -> Dict:
        d = {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "goal_ancestry"}
        d["goal_chain"] = self.goal_ancestry.chain() if self.goal_ancestry else ""
        return d

@dataclass
class Handoff:
    from_agent: str; to_agent: str
    payload: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    payload_schema: Dict[str, Dict] = field(default_factory=dict)

    def validate_payload(self) -> Tuple[bool, str]:
        if not self.payload_schema: return True, "OK"
        TYPE_MAP = {"str": str, "int": int, "float": (int, float), "bool": bool, "list": list, "dict": dict}
        errs = []
        for fname, rules in self.payload_schema.items():
            if fname not in self.payload:
                if rules.get("required", True): errs.append(f"Handoff payload missing '{fname}'")
                continue
            val = self.payload[fname]
            expected = rules.get("type")
            if expected:
                py_type = TYPE_MAP.get(expected)
                if py_type and not isinstance(val, py_type):
                    errs.append(f"Handoff '{fname}' expected {expected}, got {type(val).__name__}")
        return (True, "OK") if not errs else (False, "; ".join(errs))

    def to_context_str(self):
        p = [f"[Handoff from {self.from_agent}]"]
        if self.reason: p.append(f"Reason: {self.reason}")
        if self.payload: p.append(f"Data: {json.dumps(self.payload, ensure_ascii=False)[:2000]}")
        return "\n".join(p)
