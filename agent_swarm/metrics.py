"""Metrics and tracing — histogram/percentile, span hierarchy."""
from __future__ import annotations
import time, uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class Span:
    name: str; span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    parent_id: str = ""; task_id: str = ""
    start_time: float = 0.0; end_time: float = 0.0
    status: str = "ok"; detail: str = ""
    children: List[str] = field(default_factory=list)
    @property
    def duration_ms(self): return round((self.end_time - self.start_time) * 1000, 2) if self.end_time else 0
    def to_dict(self):
        return {"name": self.name, "span_id": self.span_id, "parent_id": self.parent_id,
                "task_id": self.task_id, "duration_ms": self.duration_ms, "status": self.status,
                "detail": self.detail[:200], "children": self.children}

class Tracer:
    def __init__(self): self.spans: List[Span] = []; self._stk: List[Span] = []
    def start(self, name, task_id="") -> Span:
        pid = self._stk[-1].span_id if self._stk else ""
        s = Span(name=name, parent_id=pid, task_id=task_id, start_time=time.time())
        if self._stk: self._stk[-1].children.append(s.span_id)
        self.spans.append(s); self._stk.append(s); return s
    def end(self, status="ok", detail=""):
        if self._stk:
            s = self._stk.pop(); s.end_time = time.time(); s.status = status; s.detail = detail[:200]; return s
    def to_dict(self): return {"total_spans": len(self.spans), "spans": [s.to_dict() for s in self.spans]}

class MetricsCollector:
    """Centralized operational metrics with histogram/percentile support."""
    def __init__(self):
        self.total_runs = 0; self.total_tasks = 0
        self.succeeded_tasks = 0; self.failed_tasks = 0
        self.total_retries = 0; self.total_llm_calls = 0
        self.total_approval_wait_ms = 0.0; self.approvals_requested = 0
        self.planner_uses = 0; self.planner_fallbacks = 0
        self.evolution_attempts = 0; self.evolution_accepted = 0; self.evolution_rejected = 0
        self.shadow_promotions = 0; self.shadow_rejections = 0
        self.checkpoint_resumes = 0
        self._task_durations: List[float] = []
        self._approval_waits: List[float] = []
        self._validation_failures: Dict[str, int] = defaultdict(int)

    def record_run(self, meta: Dict):
        self.total_runs += 1; self.total_tasks += meta.get("total_tasks", 0)
        self.succeeded_tasks += meta.get("succeeded", 0); self.failed_tasks += meta.get("failed", 0)
        self.total_llm_calls += meta.get("llm_calls_used", 0)
    def record_task_duration(self, ms: float): self._task_durations.append(ms)
    def record_retry(self): self.total_retries += 1
    def record_approval_wait(self, ms: float): self._approval_waits.append(ms)
    def record_validation_failure(self, reason: str): self._validation_failures[reason[:80]] += 1

    @staticmethod
    def _percentiles(values: List[float]) -> Dict:
        if not values: return {"count": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0, "min": 0, "max": 0}
        s = sorted(values); n = len(s)
        return {"count": n, "avg": round(sum(s) / n, 1),
                "p50": round(s[n // 2], 1),
                "p95": round(s[int(n * 0.95)] if n >= 20 else s[-1], 1),
                "p99": round(s[int(n * 0.99)] if n >= 100 else s[-1], 1),
                "min": round(s[0], 1), "max": round(s[-1], 1)}

    def to_dict(self) -> Dict:
        return {
            "total_runs": self.total_runs, "total_tasks": self.total_tasks,
            "succeeded_tasks": self.succeeded_tasks, "failed_tasks": self.failed_tasks,
            "success_rate": round(self.succeeded_tasks / max(self.total_tasks, 1), 3),
            "task_duration_ms": self._percentiles(self._task_durations),
            "approval_wait_ms": self._percentiles(self._approval_waits),
            "total_retries": self.total_retries, "total_llm_calls": self.total_llm_calls,
            "planner_uses": self.planner_uses, "planner_fallbacks": self.planner_fallbacks,
            "planner_fallback_ratio": round(self.planner_fallbacks / max(self.planner_uses + self.planner_fallbacks, 1), 3),
            "evolution": {"attempts": self.evolution_attempts, "accepted": self.evolution_accepted, "rejected": self.evolution_rejected},
            "shadow": {"promotions": self.shadow_promotions, "rejections": self.shadow_rejections},
            "approvals_requested": self.approvals_requested,
            "checkpoint_resumes": self.checkpoint_resumes,
            "top_validation_failures": dict(sorted(self._validation_failures.items(), key=lambda x: -x[1])[:10]),
        }
