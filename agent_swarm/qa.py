"""QA System for Agent Swarm.

Issue taxonomy, health scoring, and QA review gate.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Awaitable


class IssueSeverity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class IssueCategory(Enum):
    SECURITY = "security"
    PERFORMANCE = "performance"
    CORRECTNESS = "correctness"
    STYLE = "style"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    ARCHITECTURE = "architecture"


# Severity weights for health score deduction
SEVERITY_WEIGHTS = {
    IssueSeverity.CRITICAL: 30,
    IssueSeverity.HIGH: 15,
    IssueSeverity.MEDIUM: 5,
    IssueSeverity.LOW: 2,
    IssueSeverity.INFO: 0,
}


@dataclass
class QAIssue:
    severity: IssueSeverity
    category: IssueCategory
    description: str
    file_path: str = ""
    line_number: int = 0
    suggestion: str = ""

    @property
    def weight(self) -> int:
        return SEVERITY_WEIGHTS.get(self.severity, 0)


@dataclass
class HealthScore:
    score: float  # 0-100
    deductions: Dict[str, float] = field(default_factory=dict)

    @staticmethod
    def from_issues(issues: List[QAIssue], max_score: float = 100.0) -> "HealthScore":
        deductions: Dict[str, float] = {}
        total_deduction = 0.0
        for issue in issues:
            key = f"{issue.severity.value}:{issue.category.value}"
            weight = issue.weight
            deductions[key] = deductions.get(key, 0) + weight
            total_deduction += weight

        score = max(0.0, max_score - total_deduction)
        return HealthScore(score=score, deductions=deductions)

    @property
    def grade(self) -> str:
        if self.score >= 90:
            return "A"
        elif self.score >= 80:
            return "B"
        elif self.score >= 70:
            return "C"
        elif self.score >= 60:
            return "D"
        return "F"


@dataclass
class QAReport:
    issues: List[QAIssue] = field(default_factory=list)
    health_score: Optional[HealthScore] = None
    summary: str = ""

    def compute_health(self) -> HealthScore:
        self.health_score = HealthScore.from_issues(self.issues)
        return self.health_score

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.HIGH)

    def issues_by_severity(self) -> Dict[IssueSeverity, List[QAIssue]]:
        result: Dict[IssueSeverity, List[QAIssue]] = {}
        for issue in self.issues:
            result.setdefault(issue.severity, []).append(issue)
        return result

    def issues_by_category(self) -> Dict[IssueCategory, List[QAIssue]]:
        result: Dict[IssueCategory, List[QAIssue]] = {}
        for issue in self.issues:
            result.setdefault(issue.category, []).append(issue)
        return result

    def format_summary(self) -> str:
        if self.health_score is None:
            self.compute_health()
        lines = [
            f"QA Report — Health Score: {self.health_score.score:.0f}/100 (Grade: {self.health_score.grade})",
            f"Issues: {len(self.issues)} total "
            f"({self.critical_count} critical, {self.high_count} high)",
        ]
        if self.summary:
            lines.append(f"Summary: {self.summary}")
        return "\n".join(lines)


class QAReviewGate:
    """QA-based review gate compatible with RunMachine ReviewGate interface."""

    def __init__(
        self,
        analyzers: Optional[List[Callable[..., Awaitable[List[QAIssue]]]]] = None,
        min_health_score: float = 70.0,
        block_on_critical: bool = True,
    ):
        self._analyzers = analyzers or []
        self._min_health_score = min_health_score
        self._block_on_critical = block_on_critical

    async def review(self, run_id: str, proof: Any, context: Optional[Dict] = None) -> Dict[str, Any]:
        """Run QA analysis and return review result compatible with ReviewGate."""
        all_issues: List[QAIssue] = []
        for analyzer in self._analyzers:
            try:
                issues = await analyzer(run_id, proof)
                all_issues.extend(issues)
            except Exception:
                pass

        report = QAReport(issues=all_issues)
        health = report.compute_health()

        passed = health.score >= self._min_health_score
        if self._block_on_critical and report.critical_count > 0:
            passed = False

        return {
            "passed": passed,
            "score": health.score,
            "grade": health.grade,
            "issues_count": len(all_issues),
            "critical_count": report.critical_count,
            "report": report.format_summary(),
        }
