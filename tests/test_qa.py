"""Tests for agent_swarm.qa module."""
import asyncio
import pytest

from agent_swarm.qa import (
    IssueSeverity, IssueCategory, SEVERITY_WEIGHTS,
    QAIssue, HealthScore, QAReport, QAReviewGate,
)


def _make_issue(severity=IssueSeverity.MEDIUM, category=IssueCategory.CORRECTNESS, desc="test issue"):
    return QAIssue(severity=severity, category=category, description=desc)


class TestIssueSeverity:
    def test_values(self):
        assert IssueSeverity.CRITICAL.value == "critical"
        assert IssueSeverity.HIGH.value == "high"
        assert IssueSeverity.MEDIUM.value == "medium"
        assert IssueSeverity.LOW.value == "low"
        assert IssueSeverity.INFO.value == "info"


class TestIssueCategory:
    def test_values(self):
        assert IssueCategory.SECURITY.value == "security"
        assert IssueCategory.PERFORMANCE.value == "performance"
        assert IssueCategory.CORRECTNESS.value == "correctness"
        assert IssueCategory.STYLE.value == "style"
        assert IssueCategory.DOCUMENTATION.value == "documentation"
        assert IssueCategory.TESTING.value == "testing"
        assert IssueCategory.ARCHITECTURE.value == "architecture"


class TestQAIssue:
    def test_weight_property(self):
        for sev, expected in SEVERITY_WEIGHTS.items():
            issue = _make_issue(severity=sev)
            assert issue.weight == expected


class TestHealthScore:
    def test_no_issues_gives_100(self):
        hs = HealthScore.from_issues([])
        assert hs.score == 100.0
        assert hs.deductions == {}

    def test_mixed_issues(self):
        issues = [
            _make_issue(IssueSeverity.HIGH, IssueCategory.SECURITY),
            _make_issue(IssueSeverity.LOW, IssueCategory.STYLE),
        ]
        hs = HealthScore.from_issues(issues)
        assert hs.score == 100.0 - 15 - 2  # 83

    def test_floor_at_zero(self):
        issues = [_make_issue(IssueSeverity.CRITICAL) for _ in range(5)]
        hs = HealthScore.from_issues(issues)
        assert hs.score == 0.0

    def test_grade_a(self):
        assert HealthScore(score=95).grade == "A"
        assert HealthScore(score=90).grade == "A"

    def test_grade_b(self):
        assert HealthScore(score=85).grade == "B"
        assert HealthScore(score=80).grade == "B"

    def test_grade_c(self):
        assert HealthScore(score=75).grade == "C"

    def test_grade_d(self):
        assert HealthScore(score=65).grade == "D"

    def test_grade_f(self):
        assert HealthScore(score=50).grade == "F"
        assert HealthScore(score=0).grade == "F"


class TestQAReport:
    def test_compute_health(self):
        report = QAReport(issues=[_make_issue(IssueSeverity.MEDIUM)])
        hs = report.compute_health()
        assert hs.score == 95.0
        assert report.health_score is hs

    def test_critical_count(self):
        report = QAReport(issues=[
            _make_issue(IssueSeverity.CRITICAL),
            _make_issue(IssueSeverity.CRITICAL),
            _make_issue(IssueSeverity.HIGH),
        ])
        assert report.critical_count == 2

    def test_high_count(self):
        report = QAReport(issues=[
            _make_issue(IssueSeverity.HIGH),
            _make_issue(IssueSeverity.MEDIUM),
        ])
        assert report.high_count == 1

    def test_issues_by_severity(self):
        issues = [
            _make_issue(IssueSeverity.HIGH),
            _make_issue(IssueSeverity.HIGH),
            _make_issue(IssueSeverity.LOW),
        ]
        grouped = QAReport(issues=issues).issues_by_severity()
        assert len(grouped[IssueSeverity.HIGH]) == 2
        assert len(grouped[IssueSeverity.LOW]) == 1

    def test_issues_by_category(self):
        issues = [
            _make_issue(category=IssueCategory.SECURITY),
            _make_issue(category=IssueCategory.SECURITY),
            _make_issue(category=IssueCategory.STYLE),
        ]
        grouped = QAReport(issues=issues).issues_by_category()
        assert len(grouped[IssueCategory.SECURITY]) == 2
        assert len(grouped[IssueCategory.STYLE]) == 1

    def test_format_summary(self):
        report = QAReport(
            issues=[_make_issue(IssueSeverity.CRITICAL)],
            summary="Needs work",
        )
        text = report.format_summary()
        assert "70/100" in text
        assert "Grade: C" in text
        assert "1 critical" in text
        assert "Summary: Needs work" in text


class TestQAReviewGate:
    def _run(self, coro):
        return asyncio.run(coro)

    def test_passes_above_threshold(self):
        gate = QAReviewGate(analyzers=[], min_health_score=70.0)
        result = self._run(gate.review("r1", {}))
        assert result["passed"] is True
        assert result["score"] == 100.0

    def test_fails_below_threshold(self):
        async def bad_analyzer(run_id, proof):
            return [_make_issue(IssueSeverity.CRITICAL) for _ in range(3)]

        gate = QAReviewGate(analyzers=[bad_analyzer], min_health_score=70.0, block_on_critical=False)
        result = self._run(gate.review("r1", {}))
        # 100 - 90 = 10, below 70
        assert result["passed"] is False
        assert result["score"] == 10.0

    def test_blocks_on_critical_even_if_score_high(self):
        async def minor_critical(run_id, proof):
            return [_make_issue(IssueSeverity.CRITICAL)]

        # score = 70, meets threshold, but has critical
        gate = QAReviewGate(analyzers=[minor_critical], min_health_score=70.0, block_on_critical=True)
        result = self._run(gate.review("r1", {}))
        assert result["score"] == 70.0
        assert result["critical_count"] == 1
        assert result["passed"] is False
