"""Tests for convergence loop (HRM-inspired iterative refinement)."""
import asyncio
import pytest
from agent_swarm.convergence import (
    ConvergenceConfig, ConvergenceLoop, ConvergenceResult,
    AdaptiveHalt, HaltDecision,
)


# ── Helpers ──────────────────────────────────────────────────────

async def improving_refiner(artifact, score, feedback):
    """Refiner that improves artifact each time."""
    return artifact + 1 if isinstance(artifact, (int, float)) else artifact


async def static_refiner(artifact, score, feedback):
    """Refiner that returns artifact unchanged."""
    return artifact


async def score_evaluator(artifact):
    """Evaluator that scores based on artifact value (0-1 clamped)."""
    score = min(1.0, max(0.0, artifact / 10.0)) if isinstance(artifact, (int, float)) else 0.5
    return score, f"Score: {score:.2f}"


async def constant_evaluator(artifact):
    """Evaluator that always returns 0.8."""
    return 0.8, "constant"


async def oscillating_evaluator(artifact):
    """Evaluator that oscillates (never converges)."""
    val = artifact if isinstance(artifact, (int, float)) else 0
    score = 0.5 + 0.3 * (1 if val % 2 == 0 else -1)
    return score, f"oscillating: {score}"


# ── ConvergenceLoop Tests ────────────────────────────────────────

class TestConvergenceLoop:
    def test_check_converged_stable_scores(self):
        loop = ConvergenceLoop(ConvergenceConfig(
            stability_threshold=0.05,
            min_iterations=2,
            score_history_window=3,
        ))
        assert loop.check_converged([0.8, 0.82, 0.83]) is True
        assert loop.check_converged([0.8, 0.82, 0.83, 0.83]) is True

    def test_check_converged_unstable_scores(self):
        loop = ConvergenceLoop(ConvergenceConfig(
            stability_threshold=0.05,
            min_iterations=2,
            score_history_window=3,
        ))
        assert loop.check_converged([0.3, 0.5, 0.8]) is False

    def test_check_converged_too_few_scores(self):
        loop = ConvergenceLoop(ConvergenceConfig(min_iterations=3))
        assert loop.check_converged([0.8, 0.8]) is False

    def test_check_improving(self):
        loop = ConvergenceLoop(ConvergenceConfig(improvement_threshold=0.01))
        assert loop.check_improving([0.5, 0.6]) is True
        assert loop.check_improving([0.5, 0.505]) is False
        assert loop.check_improving([0.5]) is True  # too early

    @pytest.mark.asyncio
    async def test_run_converges(self):
        """Scores: 0.8, 0.8, 0.8 — stable from start → converges."""
        loop = ConvergenceLoop(ConvergenceConfig(
            max_iterations=10,
            min_iterations=2,
            stability_threshold=0.05,
            score_history_window=3,
        ))
        result = await loop.run(
            artifact=8,  # 0.8 score, static refiner keeps it constant
            refiner=static_refiner,
            evaluator=score_evaluator,
        )
        assert result.converged is True
        assert result.reason == "converged"
        assert result.iterations <= 10
        assert result.final_score >= 0.7
        assert len(result.score_history) >= 2

    @pytest.mark.asyncio
    async def test_run_max_iterations(self):
        loop = ConvergenceLoop(ConvergenceConfig(
            max_iterations=3,
            min_iterations=2,
            stability_threshold=0.001,  # very tight
            score_history_window=3,
        ))
        result = await loop.run(
            artifact=0,
            refiner=improving_refiner,
            evaluator=score_evaluator,
        )
        assert result.iterations == 3
        assert result.reason == "max_iterations"

    @pytest.mark.asyncio
    async def test_run_no_improvement(self):
        loop = ConvergenceLoop(ConvergenceConfig(
            max_iterations=10,
            min_iterations=2,
            improvement_threshold=0.01,
        ))
        result = await loop.run(
            artifact=5,
            refiner=static_refiner,
            evaluator=score_evaluator,
        )
        assert result.reason == "converged" or result.reason == "no_improvement"
        assert result.iterations <= 10

    @pytest.mark.asyncio
    async def test_run_with_halt(self):
        halt = AdaptiveHalt(quality_floor=0.5)
        loop = ConvergenceLoop(ConvergenceConfig(max_iterations=10))
        result = await loop.run(
            artifact=8,  # 0.8 score
            refiner=improving_refiner,
            evaluator=score_evaluator,
            halt=halt,
        )
        assert "halted" in result.reason or result.converged

    def test_result_properties(self):
        r = ConvergenceResult(
            converged=True,
            final_artifact="done",
            final_score=0.9,
            iterations=3,
            score_history=(0.5, 0.7, 0.9),
            reason="converged",
        )
        assert r.improved is True
        assert r.total_improvement == pytest.approx(0.4)

    def test_result_no_improvement(self):
        r = ConvergenceResult(
            converged=True,
            final_artifact="done",
            final_score=0.5,
            iterations=1,
            score_history=(0.5,),
            reason="converged",
        )
        assert r.improved is False
        assert r.total_improvement == 0.0


# ── AdaptiveHalt Tests ───────────────────────────────────────────

class TestAdaptiveHalt:
    def test_quality_target_met(self):
        halt = AdaptiveHalt()
        decision = halt.should_halt(
            scores=[0.5, 0.7, 0.95],
            budget_remaining=5,
            quality_target=0.9,
        )
        assert decision.halt is True
        assert "quality_target_met" in decision.reason
        assert decision.confidence > 0.9

    def test_continue_when_improving(self):
        halt = AdaptiveHalt()
        decision = halt.should_halt(
            scores=[0.3, 0.5],
            budget_remaining=5,
            quality_target=0.9,
        )
        assert decision.halt is False

    def test_budget_panic(self):
        halt = AdaptiveHalt(quality_floor=0.6, budget_panic_ratio=0.3)
        decision = halt.should_halt(
            scores=[0.5, 0.6, 0.65],
            budget_remaining=1,
            quality_target=0.9,
        )
        assert decision.halt is True
        assert "budget_low" in decision.reason

    def test_diminishing_returns(self):
        halt = AdaptiveHalt(quality_floor=0.5, marginal_threshold=0.02)
        decision = halt.should_halt(
            scores=[0.5, 0.6, 0.605, 0.608],
            budget_remaining=5,
            quality_target=0.9,
        )
        assert decision.halt is True
        assert "diminishing_returns" in decision.reason

    def test_no_scores(self):
        halt = AdaptiveHalt()
        decision = halt.should_halt([], 5)
        assert decision.halt is False
        assert decision.confidence == 0.0

    def test_halt_decision_immutable(self):
        d = HaltDecision(halt=True, reason="test", confidence=0.9)
        assert d.halt is True
        assert d.reason == "test"
