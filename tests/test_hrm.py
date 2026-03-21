"""Tests for HRM 2-tier orchestration."""
import asyncio
import pytest
from agent_swarm.hrm import (
    HRMConfig, HRMOrchestrator, HRMResult,
    HModuleState, LModuleState, HRMCycle,
)
from agent_swarm.convergence import ConvergenceConfig


# ── Helpers ──────────────────────────────────────────────────

async def simple_planner(goal, feedback, prev_score):
    """H-module: returns a plan string, adjusts based on feedback."""
    if feedback:
        return f"revised plan for: {goal} (feedback: {feedback[:30]})"
    return f"initial plan for: {goal}"


async def improving_executor(plan, feedback):
    """L-module: returns incrementally better artifact."""
    base = 5
    if "revised" in str(plan):
        base = 8
    return base + len(feedback)


async def good_evaluator(artifact):
    """Evaluator that scores based on artifact value."""
    score = min(1.0, artifact / 10.0) if isinstance(artifact, (int, float)) else 0.5
    feedback = "needs more depth" if score < 0.9 else "excellent"
    return score, feedback


async def perfect_evaluator(artifact):
    """Always returns perfect score."""
    return 1.0, "perfect"


async def bad_evaluator(artifact):
    """Always returns low score."""
    return 0.3, "insufficient"


async def stagnant_evaluator(artifact):
    """Returns fixed mediocre score."""
    return 0.65, "mediocre"


# ── Config Tests ─────────────────────────────────────────────

class TestHRMConfig:
    def test_frozen(self):
        cfg = HRMConfig()
        with pytest.raises(AttributeError):
            cfg.h_max_cycles = 10

    def test_defaults(self):
        cfg = HRMConfig()
        assert cfg.h_max_cycles == 3
        assert cfg.l_max_iterations == 5
        assert cfg.quality_target == 0.9
        assert cfg.quality_floor == 0.6


class TestHModuleState:
    def test_frozen(self):
        s = HModuleState(cycle=0, plan="test")
        with pytest.raises(AttributeError):
            s.cycle = 1


class TestLModuleState:
    def test_frozen(self):
        from agent_swarm.convergence import ConvergenceResult
        cr = ConvergenceResult(True, "art", 0.8, 3, (0.6, 0.7, 0.8), "converged")
        s = LModuleState(h_cycle=0, convergence=cr)
        with pytest.raises(AttributeError):
            s.h_cycle = 1


# ── Orchestrator Tests ───────────────────────────────────────

class TestHRMOrchestrator:
    @pytest.mark.asyncio
    async def test_quality_met_early(self):
        """Perfect evaluator should halt after first H-cycle."""
        orch = HRMOrchestrator(HRMConfig(h_max_cycles=5))
        result = await orch.run(
            goal="test",
            h_planner=simple_planner,
            l_executor=improving_executor,
            evaluator=perfect_evaluator,
        )
        assert result.success is True
        assert result.reason == "quality_met"
        assert result.h_cycles == 1
        assert result.final_score == 1.0

    @pytest.mark.asyncio
    async def test_h_max_cycles_reached(self):
        """Bad evaluator should exhaust all H-cycles."""
        orch = HRMOrchestrator(HRMConfig(
            h_max_cycles=2,
            l_convergence=ConvergenceConfig(max_iterations=2, min_iterations=1),
        ))
        result = await orch.run(
            goal="test",
            h_planner=simple_planner,
            l_executor=improving_executor,
            evaluator=bad_evaluator,
        )
        assert result.reason in ("h_max_cycles", "converged")
        assert result.h_cycles <= 2

    @pytest.mark.asyncio
    async def test_h_level_convergence(self):
        """Stagnant evaluator should trigger H-level convergence."""
        orch = HRMOrchestrator(HRMConfig(h_max_cycles=5))
        result = await orch.run(
            goal="test",
            h_planner=simple_planner,
            l_executor=improving_executor,
            evaluator=stagnant_evaluator,
        )
        assert result.reason == "converged"
        assert result.h_cycles <= 5

    @pytest.mark.asyncio
    async def test_improving_across_h_cycles(self):
        """With revision, L-module should improve across H-cycles."""
        orch = HRMOrchestrator(HRMConfig(
            h_max_cycles=3,
            quality_target=0.95,
            l_convergence=ConvergenceConfig(max_iterations=3, min_iterations=1),
        ))
        result = await orch.run(
            goal="improve",
            h_planner=simple_planner,
            l_executor=improving_executor,
            evaluator=good_evaluator,
        )
        assert len(result.cycles) >= 1
        # Should have multiple cycles if not perfect immediately
        assert result.final_score > 0

    @pytest.mark.asyncio
    async def test_result_properties(self):
        orch = HRMOrchestrator(HRMConfig(h_max_cycles=2))
        result = await orch.run(
            goal="test",
            h_planner=simple_planner,
            l_executor=improving_executor,
            evaluator=good_evaluator,
        )
        assert isinstance(result.cycles, tuple)
        assert result.total_l_iterations > 0
        assert all(isinstance(c, HRMCycle) for c in result.cycles)

    @pytest.mark.asyncio
    async def test_cycle_records_h_and_l_state(self):
        orch = HRMOrchestrator(HRMConfig(h_max_cycles=1))
        result = await orch.run(
            goal="test",
            h_planner=simple_planner,
            l_executor=improving_executor,
            evaluator=good_evaluator,
        )
        cycle = result.cycles[0]
        assert isinstance(cycle.h_state, HModuleState)
        assert isinstance(cycle.l_state, LModuleState)
        assert cycle.h_state.cycle == 0
        assert cycle.h_state.revised is False
        assert cycle.l_state.h_cycle == 0

    @pytest.mark.asyncio
    async def test_revised_flag_on_replan(self):
        """Second H-cycle should have revised=True."""
        orch = HRMOrchestrator(HRMConfig(h_max_cycles=3))
        result = await orch.run(
            goal="test",
            h_planner=simple_planner,
            l_executor=improving_executor,
            evaluator=stagnant_evaluator,
        )
        if len(result.cycles) >= 2:
            assert result.cycles[1].h_state.revised is True

    @pytest.mark.asyncio
    async def test_default_config(self):
        orch = HRMOrchestrator()
        assert orch.config.h_max_cycles == 3
        assert orch.config.quality_target == 0.9
