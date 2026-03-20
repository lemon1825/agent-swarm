"""Tests for agent_swarm.retro module."""
import time
import pytest
from agent_swarm.retro import Retro, RetroReport
from agent_swarm.telemetry import TelemetryEvent


class MockReader:
    def __init__(self, events):
        self._events = events

    def read_all(self):
        return self._events


def _now():
    return time.time()


class TestRetroReport:
    def test_defaults(self):
        r = RetroReport()
        assert r.period_days == 7
        assert r.total_runs == 0
        assert r.successful_runs == 0
        assert r.failed_runs == 0
        assert r.failure_patterns == []
        assert r.skill_evolution == []
        assert r.cost_summary == {}
        assert r.improvements == []
        assert r.action_items == []

    def test_success_rate_zero_runs(self):
        r = RetroReport(total_runs=0)
        assert r.success_rate == 0.0

    def test_success_rate_calculation(self):
        r = RetroReport(total_runs=10, successful_runs=7, failed_runs=3)
        assert r.success_rate == pytest.approx(0.7)

    def test_format_report_basic(self):
        r = RetroReport(total_runs=5, successful_runs=4, failed_runs=1)
        text = r.format_report()
        assert "# Retrospective Report" in text
        assert "5 total" in text
        assert "4 success" in text
        assert "80.0%" in text

    def test_format_report_with_sections(self):
        r = RetroReport(
            total_runs=2, successful_runs=1, failed_runs=1,
            failure_patterns=[{"pattern": "timeout", "count": 3}],
            skill_evolution=[{"name": "debug", "action": "promoted"}],
            improvements=["Fix timeouts"],
            action_items=["Add retry logic"],
        )
        text = r.format_report()
        assert "## Failure Patterns" in text
        assert "timeout: 3 occurrences" in text
        assert "## Skill Evolution" in text
        assert "debug: promoted" in text
        assert "## Suggested Improvements" in text
        assert "## Action Items" in text
        assert "- [ ] Add retry logic" in text


class TestRetro:
    def test_no_reader_returns_empty_report(self):
        retro = Retro()
        report = retro.generate()
        assert report.total_runs == 0
        assert report.period_days == 7

    def test_generate_with_mock_reader(self):
        now = _now()
        events = [
            TelemetryEvent("run_completed", {"success": True}, timestamp=now - 100),
            TelemetryEvent("run_completed", {"success": False}, timestamp=now - 200),
            TelemetryEvent("run_completed", {"success": True}, timestamp=now - 300),
            TelemetryEvent("error_occurred", {"error_type": "timeout"}, timestamp=now - 150),
            TelemetryEvent("error_occurred", {"error_type": "timeout"}, timestamp=now - 250),
            TelemetryEvent("skill_promoted", {"skill_name": "debug"}, timestamp=now - 50),
        ]
        retro = Retro(telemetry_reader=MockReader(events))
        report = retro.generate(period_days=7)
        assert report.total_runs == 3
        assert report.successful_runs == 2
        assert report.failed_runs == 1
        assert report.success_rate == pytest.approx(2 / 3)
        assert len(report.failure_patterns) == 1
        assert report.failure_patterns[0]["pattern"] == "timeout"
        assert report.failure_patterns[0]["count"] == 2
        assert len(report.skill_evolution) == 1
        assert report.skill_evolution[0]["name"] == "debug"

    def test_suggest_improvements_low_success_rate(self):
        report = RetroReport(total_runs=10, successful_runs=3, failed_runs=7)
        retro = Retro()
        suggestions = retro.suggest_improvements(report)
        assert any("below 50%" in s for s in suggestions)

    def test_suggest_improvements_medium_success_rate(self):
        report = RetroReport(total_runs=10, successful_runs=7, failed_runs=3)
        retro = Retro()
        suggestions = retro.suggest_improvements(report)
        assert any("below 80%" in s for s in suggestions)

    def test_suggest_improvements_recurring_failures(self):
        report = RetroReport(
            total_runs=5, successful_runs=2, failed_runs=3,
            failure_patterns=[{"pattern": "timeout", "count": 5}],
        )
        retro = Retro()
        suggestions = retro.suggest_improvements(report)
        assert any("Recurring failure" in s for s in suggestions)

    def test_suggest_improvements_no_runs(self):
        report = RetroReport(total_runs=0)
        retro = Retro()
        suggestions = retro.suggest_improvements(report)
        assert any("No runs recorded" in s for s in suggestions)

    def test_suggest_improvements_high_token_usage(self):
        report = RetroReport(
            total_runs=5, successful_runs=5,
            cost_summary={"avg_tokens_per_run": 60000},
        )
        retro = Retro()
        suggestions = retro.suggest_improvements(report)
        assert any("token usage" in s for s in suggestions)

    def test_suggest_improvements_no_skill_evolution(self):
        report = RetroReport(total_runs=10, successful_runs=10)
        retro = Retro()
        suggestions = retro.suggest_improvements(report)
        assert any("No skill promotions" in s for s in suggestions)
