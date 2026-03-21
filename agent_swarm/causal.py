"""Causal Attribution Graph — trace root causes through agent DAG execution.

Based on Causal Inference methodology (Pearl, Rubin):
- Track causal relationships between agent actions and outcomes
- Attribution: which agent's decision influenced the final result?
- Root cause analysis: trace failure chains backwards

Like a detective's evidence board: pins (agent actions) connected by
strings (causal links) showing how one event led to another. When
something goes wrong, follow the strings backwards to find the source.

Usage:
    from agent_swarm.causal import CausalGraph, CausalEdge

    graph = CausalGraph()
    graph = graph.add_edge("research", "analysis", 0.8, "dependency")
    graph = graph.add_edge("analysis", "report", 0.9, "dependency")

    # Trace root cause of a failure
    chain = graph.trace_root_cause("report")
    print(graph.attribution_report())
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple


__all__ = [
    "CausalEdge",
    "CausalGraph",
    "CausalAttribution",
    "compute_influence",
    "counterfactual_influence",
]


@dataclass(frozen=True)
class CausalEdge:
    """A causal relationship between two tasks."""
    cause_task: str
    effect_task: str
    influence_score: float  # 0.0 to 1.0
    mechanism: str  # "dependency", "context", "retry", "escalation"
    metadata: Tuple[Tuple[str, str], ...] = ()  # frozen dict alternative

    def with_score(self, score: float) -> "CausalEdge":
        """Return new edge with updated score."""
        return CausalEdge(
            cause_task=self.cause_task,
            effect_task=self.effect_task,
            influence_score=score,
            mechanism=self.mechanism,
            metadata=self.metadata,
        )


@dataclass(frozen=True)
class CausalAttribution:
    """Attribution of a task's outcome to its causal factors."""
    task_id: str
    total_influence: float
    contributing_tasks: Tuple[Tuple[str, float], ...]  # (task_id, influence)
    root_causes: Tuple[str, ...]  # tasks with no incoming edges

    @property
    def primary_cause(self) -> Optional[str]:
        """The task with highest influence."""
        if not self.contributing_tasks:
            return None
        return max(self.contributing_tasks, key=lambda x: x[1])[0]


class CausalGraph:
    """Immutable DAG of causal relationships between agent actions.

    Each mutation method returns a new CausalGraph (immutable pattern).
    """

    def __init__(self, edges: Optional[Tuple[CausalEdge, ...]] = None,
                 task_outcomes: Optional[Dict[str, bool]] = None):
        self._edges = edges or ()
        self._outcomes: Dict[str, bool] = dict(task_outcomes) if task_outcomes else {}

    @property
    def edges(self) -> Tuple[CausalEdge, ...]:
        return self._edges

    @property
    def task_ids(self) -> Set[str]:
        """All task IDs in the graph."""
        ids: Set[str] = set()
        for e in self._edges:
            ids.add(e.cause_task)
            ids.add(e.effect_task)
        return ids

    def add_edge(
        self,
        cause: str,
        effect: str,
        influence: float,
        mechanism: str = "dependency",
    ) -> "CausalGraph":
        """Add a causal edge. Returns new CausalGraph."""
        edge = CausalEdge(
            cause_task=cause,
            effect_task=effect,
            influence_score=max(0.0, min(1.0, influence)),
            mechanism=mechanism,
        )
        return CausalGraph(
            edges=self._edges + (edge,),
            task_outcomes=self._outcomes,
        )

    def record_outcome(self, task_id: str, success: bool) -> "CausalGraph":
        """Record a task outcome. Returns new CausalGraph."""
        new_outcomes = dict(self._outcomes)
        new_outcomes[task_id] = success
        return CausalGraph(edges=self._edges, task_outcomes=new_outcomes)

    def get_causes(self, task_id: str) -> List[CausalEdge]:
        """Get all direct causes of a task."""
        return [e for e in self._edges if e.effect_task == task_id]

    def get_effects(self, task_id: str) -> List[CausalEdge]:
        """Get all direct effects of a task."""
        return [e for e in self._edges if e.cause_task == task_id]

    def trace_root_cause(self, task_id: str, max_depth: int = 10) -> List[CausalEdge]:
        """Trace the causal chain backwards from a task to its root causes.

        max_depth limits BFS levels (graph depth), not total nodes visited.
        Returns edges in reverse order (from effect back to root cause).
        """
        chain: List[CausalEdge] = []
        visited: Set[str] = set()
        current_level = [task_id]

        for _depth in range(max_depth):
            if not current_level:
                break

            next_level: List[str] = []
            for current in current_level:
                if current in visited:
                    continue
                visited.add(current)

                causes = self.get_causes(current)
                for edge in causes:
                    chain.append(edge)
                    if edge.cause_task not in visited:
                        next_level.append(edge.cause_task)

            current_level = next_level

        return chain

    def find_root_tasks(self) -> List[str]:
        """Find tasks with no incoming causal edges (root causes)."""
        all_effects = {e.effect_task for e in self._edges}
        all_causes = {e.cause_task for e in self._edges}
        return sorted(all_causes - all_effects)

    def attribute(self, task_id: str) -> CausalAttribution:
        """Compute causal attribution for a task.

        Traces all causal paths and computes influence scores.
        """
        chain = self.trace_root_cause(task_id)

        # Aggregate influence by contributing task
        contributions: Dict[str, float] = {}
        for edge in chain:
            cause = edge.cause_task
            contributions[cause] = contributions.get(cause, 0.0) + edge.influence_score

        # Normalize
        total = sum(contributions.values())
        if total > 0:
            contributions = {k: v / total for k, v in contributions.items()}

        root_tasks = tuple(
            t for t in self.find_root_tasks()
            if t in contributions
        )

        return CausalAttribution(
            task_id=task_id,
            total_influence=total,
            contributing_tasks=tuple(
                sorted(contributions.items(), key=lambda x: -x[1])
            ),
            root_causes=root_tasks,
        )

    def attribution_report(self) -> str:
        """Generate a human-readable attribution report."""
        if not self._edges:
            return "[Empty CausalGraph]"

        lines = ["Causal Attribution Report", "=" * 40]

        # Root causes
        roots = self.find_root_tasks()
        lines.append(f"Root causes: {', '.join(roots) if roots else 'none'}")
        lines.append(f"Total edges: {len(self._edges)}")
        lines.append(f"Total tasks: {len(self.task_ids)}")

        # Per-mechanism breakdown
        mechanisms: Dict[str, int] = {}
        for e in self._edges:
            mechanisms[e.mechanism] = mechanisms.get(e.mechanism, 0) + 1
        lines.append(f"Mechanisms: {mechanisms}")

        # Failed tasks and their causes
        failed = [t for t, s in self._outcomes.items() if not s]
        if failed:
            lines.append("")
            lines.append("Failed tasks:")
            for tid in failed:
                attr = self.attribute(tid)
                if attr.contributing_tasks:
                    top = attr.contributing_tasks[:3]
                    causes_str = ", ".join(
                        f"{t}({s:.2f})" for t, s in top
                    )
                    lines.append(f"  {tid} ← {causes_str}")
                else:
                    lines.append(f"  {tid} (no causal chain)")

        # Influence heatmap
        lines.append("")
        lines.append("Causal edges:")
        for e in self._edges:
            bar = "#" * int(e.influence_score * 20)
            outcome_c = self._outcomes.get(e.cause_task)
            outcome_e = self._outcomes.get(e.effect_task)
            c_mark = "+" if outcome_c else ("-" if outcome_c is False else "?")
            e_mark = "+" if outcome_e else ("-" if outcome_e is False else "?")
            lines.append(
                f"  [{c_mark}]{e.cause_task} → [{e_mark}]{e.effect_task} "
                f"|{bar}| {e.influence_score:.2f} ({e.mechanism})"
            )

        return "\n".join(lines)

    @staticmethod
    def from_dag_results(results: Dict[str, object], tasks: list) -> "CausalGraph":
        """Build a CausalGraph from DAG execution results with measured influence.

        Uses compute_influence() for data-driven causal strength instead of
        fixed scores. Falls back to heuristic if result lacks metrics.

        Args:
            results: Dict of task_id → TaskResult (with duration_ms, tokens_used, etc.)
            tasks: List of SubTask objects with dependencies

        Returns:
            CausalGraph populated from execution data
        """
        graph = CausalGraph()

        for task in tasks:
            task_id = task.id if hasattr(task, 'id') else str(task)
            deps = task.dependencies if hasattr(task, 'dependencies') else []

            for dep_id in deps:
                dep_result = results.get(dep_id)
                effect_result = results.get(task_id)
                influence = compute_influence(dep_result, effect_result)
                graph = graph.add_edge(dep_id, task_id, influence, "dependency")

        for tid, result in results.items():
            success = getattr(result, 'success', False)
            graph = graph.record_outcome(tid, success)

        return graph


# ================================================================
#  Measured Influence (replaces fixed 0.8/0.3)
# ================================================================

def compute_influence(cause_result: Optional[object], effect_result: Optional[object]) -> float:
    """Compute causal influence score from actual execution data.

    Like measuring how much fuel (cause) contributed to engine output (effect):
    considers output volume, execution time, and success signal.

    Factors:
    - success_signal: did the cause succeed? (weight: 0.4)
    - output_volume: how much did the cause produce? (weight: 0.3)
    - time_ratio: how fast was the cause relative to the effect? (weight: 0.3)

    Returns:
        Float 0.0–1.0 representing causal influence strength
    """
    if cause_result is None:
        return 0.2  # unknown cause = low influence

    cause_success = getattr(cause_result, 'success', False)
    cause_output = getattr(cause_result, 'output', '') or ''
    cause_duration = getattr(cause_result, 'duration_ms', 0.0) or 0.0
    cause_tokens = getattr(cause_result, 'tokens_used', 0) or 0

    effect_duration = 0.0
    if effect_result is not None:
        effect_duration = getattr(effect_result, 'duration_ms', 0.0) or 0.0

    # Factor 1: Success signal (0.4 weight)
    success_score = 0.8 if cause_success else 0.3

    # Factor 2: Output volume — more output = more influence (0.3 weight)
    output_len = len(cause_output)
    if output_len > 500:
        volume_score = 1.0
    elif output_len > 100:
        volume_score = 0.7
    elif output_len > 0:
        volume_score = 0.4
    else:
        volume_score = 0.1

    # Factor 3: Time ratio — if cause took significant time, it did real work (0.3 weight)
    if cause_duration > 0 and effect_duration > 0:
        ratio = cause_duration / (cause_duration + effect_duration)
        time_score = min(1.0, ratio * 2)  # normalize: 50% of total time = 1.0
    elif cause_duration > 0:
        time_score = 0.7  # cause did work, effect unknown
    else:
        time_score = 0.5  # no timing data

    influence = success_score * 0.4 + volume_score * 0.3 + time_score * 0.3
    return max(0.0, min(1.0, influence))


def counterfactual_influence(
    graph: CausalGraph,
    task_id: str,
    results: Dict[str, object],
) -> float:
    """Estimate counterfactual influence: "What if this task hadn't run?"

    Computes the fraction of downstream tasks that depend on this task,
    weighted by their success. Higher = removing this task would hurt more.

    Args:
        graph: The causal graph
        task_id: Task to evaluate counterfactually
        results: Execution results

    Returns:
        0.0 (no impact) to 1.0 (critical dependency)
    """
    effects = graph.get_effects(task_id)
    if not effects:
        return 0.0

    # Recursively find all downstream tasks
    downstream: Set[str] = set()
    queue = [e.effect_task for e in effects]
    while queue:
        current = queue.pop(0)
        if current in downstream:
            continue
        downstream.add(current)
        for e in graph.get_effects(current):
            queue.append(e.effect_task)

    if not downstream:
        return 0.0

    # Weight by success: successful downstream tasks that depended on us
    successful = sum(
        1 for tid in downstream
        if tid in results and getattr(results[tid], 'success', False)
    )

    total_tasks = len(graph.task_ids) - 1  # exclude self
    if total_tasks <= 0:
        return 0.0

    # Combine: fraction of all tasks that are downstream * success rate
    reach = len(downstream) / total_tasks
    success_rate = successful / len(downstream) if downstream else 0

    return min(1.0, reach * 0.6 + success_rate * 0.4)
