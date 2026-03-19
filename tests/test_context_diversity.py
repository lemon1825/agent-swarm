"""Tests for context_diversity.py — ContextDiversityScorer, exclude_self_context."""
import pytest
from dataclasses import dataclass, field
from typing import Optional, List

from agent_swarm.context_diversity import (
    ContextDiversityScorer, AgentDiversityScore, DiversityReport,
    exclude_self_context, diversity_report,
)


@dataclass
class _MockResult:
    output: Optional[str] = None
    error: Optional[str] = None
    role: str = ""
    validation_failures: List[str] = field(default_factory=list)

    @property
    def success(self):
        return self.error is None and not self.validation_failures


# ── ContextDiversityScorer ──

def test_scorer_empty_results():
    scorer = ContextDiversityScorer()
    report = scorer.score({"results": {}})
    assert report.avg_diversity == 0.0
    assert report.agent_scores == []


def test_scorer_single_agent():
    scorer = ContextDiversityScorer()
    result = {
        "results": {
            "t1": _MockResult(output="The quick brown fox jumps over the lazy dog", role="Writer"),
        }
    }
    report = scorer.score(result)
    assert len(report.agent_scores) == 1
    assert 0.0 <= report.avg_diversity <= 1.0


def test_scorer_diverse_agents():
    scorer = ContextDiversityScorer()
    result = {
        "results": {
            "research": _MockResult(
                output="Machine learning models use neural networks for pattern recognition in large datasets",
                role="Researcher",
            ),
            "analysis": _MockResult(
                output="The neural networks mentioned by the researcher show promising pattern recognition capabilities for production deployment",
                role="Analyst",
            ),
        }
    }
    report = scorer.score(result)
    assert len(report.agent_scores) >= 1
    assert isinstance(report, DiversityReport)


def test_scorer_high_self_reference():
    scorer = ContextDiversityScorer(self_ref_threshold=0.3)
    # Agent that echoes itself heavily
    result = {
        "results": {
            "echo": _MockResult(
                output="same words same words same words same words same words",
                role="Echo",
            ),
        }
    }
    report = scorer.score(result)
    # Single agent → self-ref compares against own output in map
    assert len(report.agent_scores) == 1


def test_scorer_skips_failed_tasks():
    scorer = ContextDiversityScorer()
    result = {
        "results": {
            "ok": _MockResult(output="good result with content", role="Worker"),
            "fail": _MockResult(error="timeout", role="Broken"),
        }
    }
    report = scorer.score(result)
    # Only successful tasks scored
    task_ids = [s.task_id for s in report.agent_scores]
    assert "fail" not in task_ids


# ── AgentDiversityScore ──

def test_agent_score_summary_line():
    score = AgentDiversityScore(
        task_id="t1", role="Researcher",
        self_reference_ratio=0.2, cross_reference_count=2,
        unique_terms_ratio=0.8, diversity_score=0.75,
        recommendation="Good diversity",
    )
    line = score.summary_line()
    assert "t1" in line
    assert "Researcher" in line
    assert "Good diversity" in line


def test_agent_score_symbols():
    high = AgentDiversityScore(task_id="t1", role="R", self_reference_ratio=0, cross_reference_count=0,
                               unique_terms_ratio=0, diversity_score=0.7, recommendation="")
    assert "✓" in high.summary_line()

    mid = AgentDiversityScore(task_id="t2", role="R", self_reference_ratio=0, cross_reference_count=0,
                              unique_terms_ratio=0, diversity_score=0.4, recommendation="")
    assert "⚠" in mid.summary_line()

    low = AgentDiversityScore(task_id="t3", role="R", self_reference_ratio=0, cross_reference_count=0,
                              unique_terms_ratio=0, diversity_score=0.2, recommendation="")
    assert "✗" in low.summary_line()


# ── DiversityReport ──

def test_report_summary():
    report = DiversityReport(
        avg_diversity=0.65,
        avg_self_reference=0.3,
        agent_scores=[
            AgentDiversityScore(task_id="t1", role="R", self_reference_ratio=0.3,
                                cross_reference_count=1, unique_terms_ratio=0.7,
                                diversity_score=0.65, recommendation="Good diversity"),
        ],
        recommendations=["Test recommendation"],
    )
    s = report.summary()
    assert "Context Diversity Report" in s
    assert "0.65" in s
    assert "Test recommendation" in s


# ── exclude_self_context ──

def test_exclude_self_context_basic():
    result = exclude_self_context(
        base_prompt="Analyze the data",
        agent_outputs={"researcher": "Found key insights", "analyst": "Previous analysis"},
        current_agent="analyst",
    )
    assert "Found key insights" in result
    assert "IMPORTANT CONTEXT FROM OTHER AGENTS" in result
    assert "Analyze the data" in result


def test_exclude_self_context_no_others():
    result = exclude_self_context(
        base_prompt="Analyze",
        agent_outputs={"analyst": "My own output"},
        current_agent="analyst",
    )
    # No other agents → returns base prompt unchanged
    assert result == "Analyze"


def test_exclude_self_context_multiple_others():
    result = exclude_self_context(
        base_prompt="Synthesize",
        agent_outputs={
            "a": "Output A",
            "b": "Output B",
            "c": "Output C (self)",
        },
        current_agent="c",
    )
    assert "[From a]" in result
    assert "[From b]" in result
    assert "[From c]" not in result


# ── diversity_report convenience ──

def test_diversity_report_convenience():
    result = {"results": {"t1": _MockResult(output="Some content here for analysis", role="W")}}
    report = diversity_report(result)
    assert isinstance(report, DiversityReport)
