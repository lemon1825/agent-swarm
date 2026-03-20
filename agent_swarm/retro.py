"""Retrospective System for Agent Swarm.

Analyzes telemetry data to generate retrospective reports with
success rates, failure patterns, skill evolution, and cost trends.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RetroReport:
    """Retrospective report summarizing a time period."""
    period_days: int = 7
    period_start: float = 0.0
    period_end: float = 0.0
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return self.successful_runs / self.total_runs

    failure_patterns: List[Dict[str, Any]] = field(default_factory=list)
    skill_evolution: List[Dict[str, Any]] = field(default_factory=list)
    cost_summary: Dict[str, float] = field(default_factory=dict)
    improvements: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)

    def format_report(self) -> str:
        lines = [
            f"# Retrospective Report",
            f"Period: {self.period_days} days",
            f"Runs: {self.total_runs} total, {self.successful_runs} success, {self.failed_runs} failed",
            f"Success Rate: {self.success_rate:.1%}",
            "",
        ]
        if self.failure_patterns:
            lines.append("## Failure Patterns")
            for p in self.failure_patterns:
                lines.append(f"- {p.get('pattern', 'unknown')}: {p.get('count', 0)} occurrences")
            lines.append("")
        if self.skill_evolution:
            lines.append("## Skill Evolution")
            for s in self.skill_evolution:
                lines.append(f"- {s.get('name', '?')}: {s.get('action', '?')}")
            lines.append("")
        if self.improvements:
            lines.append("## Suggested Improvements")
            for imp in self.improvements:
                lines.append(f"- {imp}")
            lines.append("")
        if self.action_items:
            lines.append("## Action Items")
            for item in self.action_items:
                lines.append(f"- [ ] {item}")
        return "\n".join(lines)


class Retro:
    """Generates retrospective reports from telemetry data."""

    def __init__(self, telemetry_reader: Optional[Any] = None):
        self._reader = telemetry_reader

    def generate(self, period_days: int = 7) -> RetroReport:
        """Analyze telemetry data for the given period and produce a report."""
        report = RetroReport(period_days=period_days)
        report.period_end = time.time()
        report.period_start = report.period_end - (period_days * 86400)

        if not self._reader:
            return report

        events = self._reader.read_all()

        # Filter to period
        period_events = [e for e in events if e.timestamp >= report.period_start]

        # Count runs
        run_events = [e for e in period_events if e.event_type == "run_completed"]
        report.total_runs = len(run_events)
        report.successful_runs = sum(1 for e in run_events if e.data.get("success", False))
        report.failed_runs = report.total_runs - report.successful_runs

        # Failure patterns
        error_events = [e for e in period_events if e.event_type == "error_occurred"]
        pattern_counts: Dict[str, int] = {}
        for e in error_events:
            pattern = e.data.get("error_type", "unknown")
            pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
        report.failure_patterns = [
            {"pattern": p, "count": c} for p, c in sorted(pattern_counts.items(), key=lambda x: -x[1])
        ]

        # Skill evolution
        skill_events = [e for e in period_events if e.event_type == "skill_promoted"]
        report.skill_evolution = [
            {"name": e.data.get("skill_name", "?"), "action": "promoted"} for e in skill_events
        ]

        # Cost summary
        cost_events = [e for e in run_events if "total_tokens" in e.data]
        if cost_events:
            report.cost_summary = {
                "total_tokens": sum(e.data.get("total_tokens", 0) for e in cost_events),
                "total_cost_usd": sum(e.data.get("cost_usd", 0.0) for e in cost_events),
                "avg_tokens_per_run": sum(e.data.get("total_tokens", 0) for e in cost_events) / len(cost_events),
            }

        # Generate improvements
        report.improvements = self.suggest_improvements(report)

        return report

    def suggest_improvements(self, report: Optional[RetroReport] = None) -> List[str]:
        """Heuristic improvement suggestions based on patterns."""
        if report is None:
            report = self.generate()

        suggestions = []

        if report.success_rate < 0.5 and report.total_runs > 0:
            suggestions.append("Success rate below 50% — review task decomposition strategy")
        elif report.success_rate < 0.8 and report.total_runs > 0:
            suggestions.append("Success rate below 80% — investigate common failure patterns")

        if report.failure_patterns:
            top = report.failure_patterns[0]
            if top["count"] >= 3:
                suggestions.append(f"Recurring failure: '{top['pattern']}' ({top['count']}x) — consider adding targeted skill or guard")

        if report.cost_summary.get("avg_tokens_per_run", 0) > 50000:
            suggestions.append("High average token usage — consider tighter context filtering")

        if report.total_runs == 0:
            suggestions.append("No runs recorded — ensure telemetry is enabled")

        if not report.skill_evolution and report.total_runs > 5:
            suggestions.append("No skill promotions despite multiple runs — review shadow skill thresholds")

        return suggestions
