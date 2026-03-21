"""HRM — Hierarchical Reasoning Model 2-tier orchestration.

Based on Wang et al. (2025, arXiv:2506.21734):
- H-module (slow): Abstract planning, strategy, re-planning after L converges
- L-module (fast): Rapid detailed execution, iterates to convergence
- Multi-timescale: L runs many cycles per single H update
- ACT (Adaptive Computation Time): Dynamic halt when quality sufficient

Like a general (H) and soldiers (L): the general sets strategy and reviews
after each battle, while soldiers execute rapidly on the ground. The general
only re-plans after soldiers report back — never mid-battle.

Usage:
    from agent_swarm.hrm import HRMOrchestrator, HRMConfig

    orchestrator = HRMOrchestrator(config=HRMConfig(
        h_max_cycles=3,
        l_max_iterations=5,
    ))

    result = await orchestrator.run(
        goal="Analyze market trends",
        h_planner=my_planner,
        l_executor=my_executor,
        evaluator=my_evaluator,
    )
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from .convergence import ConvergenceConfig, ConvergenceLoop, ConvergenceResult, AdaptiveHalt


__all__ = [
    "HRMConfig",
    "HModuleState",
    "LModuleState",
    "HRMCycle",
    "HRMResult",
    "HRMOrchestrator",
]


@dataclass(frozen=True)
class HRMConfig:
    """Configuration for HRM 2-tier orchestration."""
    h_max_cycles: int = 3             # max H-module re-planning cycles
    l_max_iterations: int = 5         # max L-module iterations per H cycle
    l_convergence: ConvergenceConfig = field(default_factory=lambda: ConvergenceConfig(
        max_iterations=5,
        stability_threshold=0.05,
        min_iterations=2,
        score_history_window=3,
    ))
    quality_target: float = 0.9       # overall quality target for ACT halt
    quality_floor: float = 0.6        # minimum acceptable quality


@dataclass(frozen=True)
class HModuleState:
    """State of the H-module (strategic planner) after a cycle."""
    cycle: int
    plan: Any                          # the strategic plan/decomposition
    strategy_score: float = 0.0        # how good the current strategy is
    feedback: str = ""                 # feedback from L-module results
    revised: bool = False              # whether plan was revised this cycle


@dataclass(frozen=True)
class LModuleState:
    """State of the L-module (rapid executor) after convergence."""
    h_cycle: int                       # which H-cycle this L ran under
    convergence: ConvergenceResult     # convergence loop result
    artifacts: Tuple[Any, ...] = ()    # produced artifacts


@dataclass(frozen=True)
class HRMCycle:
    """Record of a single H→L→evaluate cycle."""
    h_state: HModuleState
    l_state: LModuleState
    evaluation_score: float
    evaluation_feedback: str = ""


@dataclass(frozen=True)
class HRMResult:
    """Final result of HRM orchestration."""
    success: bool
    final_artifact: Any
    final_score: float
    h_cycles: int
    total_l_iterations: int
    cycles: Tuple[HRMCycle, ...]
    reason: str  # "quality_met", "h_max_cycles", "converged", "halted"

    @property
    def improved(self) -> bool:
        if len(self.cycles) < 2:
            return False
        return self.cycles[-1].evaluation_score > self.cycles[0].evaluation_score


# Type aliases
HPlannerFn = Callable[[str, Optional[str], float], Awaitable[Any]]
LExecutorFn = Callable[[Any, List[str]], Awaitable[Any]]
EvaluatorFn = Callable[[Any], Awaitable[Tuple[float, str]]]


class HRMOrchestrator:
    """2-tier orchestrator inspired by Hierarchical Reasoning Model.

    Execution flow:
    1. H-module plans (slow, strategic)
    2. L-module executes plan iteratively until convergence (fast, detailed)
    3. Evaluate L-module output
    4. If quality target met → halt (ACT)
    5. If not → feed evaluation back to H-module → re-plan → goto 2
    6. Repeat until H max_cycles or quality_target met
    """

    def __init__(self, config: Optional[HRMConfig] = None):
        self.config = config or HRMConfig()

    async def run(
        self,
        goal: str,
        h_planner: HPlannerFn,
        l_executor: LExecutorFn,
        evaluator: EvaluatorFn,
    ) -> HRMResult:
        """Run the HRM 2-tier orchestration.

        Args:
            goal: The top-level goal
            h_planner: async (goal, feedback, prev_score) -> plan
                H-module: produces a strategic plan/decomposition
            l_executor: async (plan, feedback_history) -> artifact
                L-module: executes the plan rapidly (used as refiner in convergence loop)
            evaluator: async (artifact) -> (score, feedback)
                Evaluates the L-module output quality

        Returns:
            HRMResult with full cycle history
        """
        cfg = self.config
        cycles: List[HRMCycle] = []
        halt = AdaptiveHalt(
            quality_floor=cfg.quality_floor,
            marginal_threshold=0.02,
        )
        convergence_loop = ConvergenceLoop(config=cfg.l_convergence)

        feedback: Optional[str] = None
        prev_score: float = 0.0
        best_artifact: Any = None
        best_score: float = 0.0
        total_l_iters: int = 0

        for h_cycle in range(cfg.h_max_cycles):
            # ── H-module: plan/re-plan ──
            plan = await h_planner(goal, feedback, prev_score)
            revised = h_cycle > 0

            # ── L-module: execute with convergence ──
            async def l_refiner(artifact: Any, score: float, fb: List[str]) -> Any:
                return await l_executor(plan, fb)

            initial_artifact = await l_executor(plan, [])
            conv_result = await convergence_loop.run(
                artifact=initial_artifact,
                refiner=l_refiner,
                evaluator=evaluator,
                halt=halt,
            )

            total_l_iters += conv_result.iterations

            h_state = HModuleState(
                cycle=h_cycle,
                plan=plan,
                strategy_score=conv_result.final_score,
                feedback=feedback or "",
                revised=revised,
            )

            l_state = LModuleState(
                h_cycle=h_cycle,
                convergence=conv_result,
                artifacts=(conv_result.final_artifact,),
            )

            # ── Evaluate ──
            eval_score, eval_feedback = await evaluator(conv_result.final_artifact)

            cycle = HRMCycle(
                h_state=h_state,
                l_state=l_state,
                evaluation_score=eval_score,
                evaluation_feedback=eval_feedback,
            )
            cycles.append(cycle)

            # Track best
            if eval_score > best_score:
                best_score = eval_score
                best_artifact = conv_result.final_artifact

            # ── ACT: check if we should halt ──
            if eval_score >= cfg.quality_target:
                return HRMResult(
                    success=True,
                    final_artifact=best_artifact,
                    final_score=best_score,
                    h_cycles=h_cycle + 1,
                    total_l_iterations=total_l_iters,
                    cycles=tuple(cycles),
                    reason="quality_met",
                )

            # ── Check H-level convergence (strategy stagnation) ──
            if h_cycle >= 1:
                h_scores = [c.evaluation_score for c in cycles]
                if len(h_scores) >= 2 and abs(h_scores[-1] - h_scores[-2]) < 0.02:
                    return HRMResult(
                        success=best_score >= cfg.quality_floor,
                        final_artifact=best_artifact,
                        final_score=best_score,
                        h_cycles=h_cycle + 1,
                        total_l_iterations=total_l_iters,
                        cycles=tuple(cycles),
                        reason="converged",
                    )

            # ── Feed back to H-module for re-planning ──
            feedback = eval_feedback
            prev_score = eval_score

        return HRMResult(
            success=best_score >= cfg.quality_floor,
            final_artifact=best_artifact,
            final_score=best_score,
            h_cycles=cfg.h_max_cycles,
            total_l_iterations=total_l_iters,
            cycles=tuple(cycles),
            reason="h_max_cycles",
        )
