"""Detailed Tracing — LangSmith-grade execution visibility.

Zero dependencies. Records every step of agent execution with
timing, token usage, cost, inputs/outputs, and dependency chain.

Usage:
    from agent_swarm.tracing import DetailedTracer

    tracer = DetailedTracer()
    swarm = Swarm(llm=my_llm, event_bus=tracer.as_event_bus())

    result = await swarm.run(...)

    # Get full trace
    trace = tracer.get_trace()
    print(trace.summary())
    print(trace.to_json())

    # Export for visualization
    tracer.export_html("trace.html")
    tracer.export_json("trace.json")
"""

__all__ = ['TraceNode', 'Trace', 'DetailedTracer']
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .events import EventBus, Event


@dataclass
class TraceNode:
    """A single traced execution step."""
    id: str
    type: str               # run_start, task_start, task_complete, task_failed, skill_update, phase_change, log
    name: str               # Human-readable name
    role: str = ""
    status: str = "pending" # pending, running, success, failed, waiting
    start_time: float = 0
    end_time: float = 0
    duration_ms: float = 0
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_total: int = 0
    cost_usd: float = 0
    input_preview: str = ""  # First 200 chars of input
    output_preview: str = "" # First 200 chars of output
    error: str = ""
    dependencies: List[str] = field(default_factory=list)
    wave: int = 0
    attempts: int = 1
    children: List['TraceNode'] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.status == "success"

    def to_dict(self) -> Dict:
        d = {
            "id": self.id, "type": self.type, "name": self.name,
            "role": self.role, "status": self.status,
            "duration_ms": round(self.duration_ms, 2),
            "tokens": {"in": self.tokens_in, "out": self.tokens_out, "total": self.tokens_total},
            "cost_usd": round(self.cost_usd, 6),
            "attempts": self.attempts,
        }
        if self.input_preview: d["input"] = self.input_preview
        if self.output_preview: d["output"] = self.output_preview
        if self.error: d["error"] = self.error
        if self.dependencies: d["deps"] = self.dependencies
        if self.children: d["children"] = [c.to_dict() for c in self.children]
        if self.metadata: d["metadata"] = self.metadata
        return d


@dataclass
class Trace:
    """Complete execution trace for a run."""
    run_id: str = ""
    mission: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: float = 0
    nodes: Dict[str, TraceNode] = field(default_factory=dict)
    events: List[Dict] = field(default_factory=list)
    total_tokens: int = 0
    total_cost_usd: float = 0
    tasks_succeeded: int = 0
    tasks_failed: int = 0

    def summary(self) -> str:
        """Human-readable trace summary."""
        dur = (self.end_time - self.start_time) if self.end_time else (time.time() - self.start_time)
        lines = [
            f"Trace: {self.mission[:60]}",
            f"  Run ID: {self.run_id}",
            f"  Duration: {dur:.2f}s",
            f"  Tasks: {self.tasks_succeeded} succeeded, {self.tasks_failed} failed",
            f"  Tokens: {self.total_tokens:,}",
            f"  Cost: ${self.total_cost_usd:.4f}",
            f"  Nodes: {len(self.nodes)}",
            "",
            "  Task Trace:",
        ]
        for node in sorted(self.nodes.values(), key=lambda n: n.start_time or 0):
            if node.type not in ("task_start", "task_complete", "task_failed"):
                continue
            status = "✓" if node.success else "✗"
            lines.append(
                f"    {status} [{node.id}] {node.name} "
                f"({node.role}) {node.duration_ms:.0f}ms "
                f"{node.tokens_total}tok ${node.cost_usd:.4f}"
            )
            if node.error:
                lines.append(f"      Error: {node.error[:80]}")

        return "\n".join(lines)

    def to_dict(self) -> Dict:
        return {
            "run_id": self.run_id, "mission": self.mission,
            "duration_s": round((self.end_time or time.time()) - self.start_time, 3),
            "tasks_succeeded": self.tasks_succeeded,
            "tasks_failed": self.tasks_failed,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "event_count": len(self.events),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)

    def critical_path(self) -> List[TraceNode]:
        """Find the critical path (longest sequential chain)."""
        task_nodes = [n for n in self.nodes.values() if n.type in ("task_complete", "task_failed")]
        if not task_nodes:
            return []

        # Build dependency graph
        by_id = {n.id: n for n in task_nodes}
        # Find the path with maximum total duration
        def path_duration(node, visited=None):
            if visited is None: visited = set()
            if node.id in visited: return 0, []
            visited.add(node.id)
            max_dur = 0
            max_path = []
            for dep in node.dependencies:
                if dep in by_id:
                    dur, path = path_duration(by_id[dep], visited.copy())
                    if dur > max_dur:
                        max_dur = dur
                        max_path = path
            return max_dur + node.duration_ms, max_path + [node]

        best_dur, best_path = 0, []
        for n in task_nodes:
            dur, path = path_duration(n)
            if dur > best_dur:
                best_dur = dur
                best_path = path
        return best_path


class DetailedTracer:
    """LangSmith-grade tracer that integrates with EventBus."""

    def __init__(self):
        self._trace = Trace()
        self._bus = EventBus()
        self._bus.on_all(self._handle_event)

    def _handle_event(self, event: Event):
        """Process events from the engine."""
        d = event.data
        self._trace.events.append(event.to_dict())

        if event.type == "run_start":
            self._trace.run_id = event.run_id
            self._trace.mission = d.get("mission", "")
            self._trace.start_time = event.timestamp
            # Create nodes for all tasks
            for t in d.get("tasks", []):
                node = TraceNode(
                    id=t.get("id", ""), type="task_pending",
                    name=t.get("name", t.get("description", "")),
                    role=t.get("role", ""),
                    dependencies=t.get("deps", t.get("dependencies", [])),
                )
                self._trace.nodes[node.id] = node

        elif event.type == "task_start":
            tid = d.get("task_id", "")
            node = self._trace.nodes.get(tid)
            if node:
                node.status = "running"
                node.start_time = event.timestamp
                node.role = d.get("role", node.role)

        elif event.type == "task_complete":
            tid = d.get("task_id", "")
            node = self._trace.nodes.get(tid)
            if node:
                node.status = "success"
                node.end_time = event.timestamp
                node.duration_ms = d.get("time_s", 0) * 1000
                node.output_preview = d.get("output", "")[:200]
                self._trace.tasks_succeeded += 1

        elif event.type == "task_failed":
            tid = d.get("task_id", "")
            node = self._trace.nodes.get(tid)
            if node:
                node.status = "failed"
                node.end_time = event.timestamp
                node.error = d.get("error", "")
                self._trace.tasks_failed += 1

        elif event.type == "task_waiting":
            tid = d.get("task_id", "")
            node = self._trace.nodes.get(tid)
            if node:
                node.status = "waiting"
                node.metadata["waiting_reason"] = d.get("reason", "approval")

        elif event.type == "skill_update":
            name = d.get("name", "")
            fitness = d.get("fitness", 0)
            self._trace.nodes[f"skill_{name}"] = TraceNode(
                id=f"skill_{name}", type="skill_update",
                name=name, metadata={"fitness": fitness},
            )

        elif event.type == "run_complete":
            self._trace.end_time = event.timestamp
            self._trace.total_tokens = sum(n.tokens_total for n in self._trace.nodes.values())
            self._trace.total_cost_usd = sum(n.cost_usd for n in self._trace.nodes.values())

    def as_event_bus(self) -> EventBus:
        """Return the EventBus to attach to Swarm."""
        return self._bus

    def get_trace(self) -> Trace:
        return self._trace

    def reset(self):
        self._trace = Trace()

    def export_json(self, path: str):
        """Export trace as JSON file."""
        with open(path, "w") as f:
            f.write(self._trace.to_json())

    def export_html(self, path: str):
        """Export trace as self-contained HTML report."""
        trace_data = self._trace.to_json()
        html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Agent Swarm Trace</title>
<style>
body{{font-family:system-ui;background:#0a0a0f;color:#e4e4ef;padding:2rem;max-width:900px;margin:0 auto}}
h1{{font-size:1.3rem;color:#5eead4}}
.summary{{background:#12121a;padding:1rem;border-radius:8px;margin:1rem 0;font-size:.85rem}}
.node{{background:#14141f;border:1px solid #1e1e2e;border-radius:8px;padding:.8rem;margin:.5rem 0}}
.node.success{{border-left:3px solid #34d399}}
.node.failed{{border-left:3px solid #f87171}}
.node-name{{font-weight:600;font-size:.9rem}}
.node-meta{{font-size:.75rem;color:#7a7a8e;margin-top:.3rem}}
pre{{background:#0a0a0f;padding:.5rem;border-radius:4px;font-size:.75rem;overflow-x:auto}}
</style></head><body>
<h1>Agent Swarm — Execution Trace</h1>
<div class="summary"><pre>{self._trace.summary()}</pre></div>
<h2 style="font-size:1rem;margin-top:2rem">Task Details</h2>
"""
        for node in sorted(self._trace.nodes.values(), key=lambda n: n.start_time or 0):
            if node.type.startswith("skill"):
                continue
            css = "success" if node.success else "failed" if node.error else ""
            html += f"""<div class="node {css}">
<div class="node-name">{'✓' if node.success else '✗'} [{node.id}] {node.name}</div>
<div class="node-meta">Role: {node.role} | {node.duration_ms:.0f}ms | {node.tokens_total} tokens | ${node.cost_usd:.4f} | Attempts: {node.attempts}</div>
"""
            if node.output_preview:
                html += f'<div class="node-meta">Output: {node.output_preview[:150]}</div>'
            if node.error:
                html += f'<div class="node-meta" style="color:#f87171">Error: {node.error}</div>'
            html += "</div>\n"

        html += f"""<h2 style="font-size:1rem;margin-top:2rem">Raw Trace</h2>
<pre>{trace_data}</pre>
</body></html>"""

        with open(path, "w") as f:
            f.write(html)
