"""Convergence Loop — HRM-inspired iterative refinement until output stabilizes.

Based on Hierarchical Reasoning Model (Wang et al., 2025, arXiv:2506.21734):
- The outer iterative refinement loop is the true driver of performance
- L-module converges before H-module updates (convergence-gated handoffs)
- Adaptive Computation Time (ACT) determines when to halt

Applied to agent workflows:
- Review stages iterate until scores stabilize (not just max_iterations)
- Convergence = score delta below threshold for N consecutive iterations
- AdaptiveHalt balances quality target vs remaining budget

Usage:
    from agent_swarm.convergence import ConvergenceLoop, ConvergenceConfig

    loop = ConvergenceLoop(config=ConvergenceConfig(
        max_iterations=5,
        stability_threshold=0.05,
    ))

    result = await loop.run(
        artifact="initial draft",
        refiner=my_refiner,
        evaluator=my_evaluator,
    )
    print(result.converged, result.final_score, result.iterations)
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, List, Optional, Tuple


__all__ = [
    "ConvergenceConfig",
    "ConvergenceResult",
    "ConvergenceLoop",
    "AdaptiveHalt",
    "HaltDecision",
]


@dataclass(frozen=True)
class ConvergenceConfig:
    """Configuration for convergence-based iteration."""
    max_iterations: int = 5           # hard ceiling on iterations
    min_iterations: int = 2           # minimum before convergence check
    stability_threshold: float = 0.05 # score delta < this = converged
    score_history_window: int = 3     # check last N scores for stability
    improvement_threshold: float = 0.01  # minimum improvement to continue


@dataclass(frozen=True)
class ConvergenceResult:
    """Result from a convergence loop run."""
    converged: bool
    final_artifact: Any
    final_score: float
    iterations: int
    score_history: Tuple[float, ...]
    reason: str  # "converged", "max_iterations", "no_improvement", "halted"

    @property
    def improved(self) -> bool:
        if len(self.score_history) < 2:
            return False
        return self.score_history[-1] > self.score_history[0]

    @property
    def total_improvement(self) -> float:
        if len(self.score_history) < 2:
            return 0.0
        return self.score_history[-1] - self.score_history[0]


# Type aliases for refiner and evaluator callbacks
Refiner = Callable[[Any, float, List[str]], Awaitable[Any]]
Evaluator = Callable[[Any], Awaitable[Tuple[float, str]]]


class ConvergenceLoop:
    """HRM-inspired iterative refinement until output stabilizes.

    The key insight from HRM: iterative refinement (the outer loop)
    contributes more to quality than sophisticated agent topology.
    Agents should iterate to convergence before escalating.

    Like a restaurant kitchen analogy: a chef tastes, adjusts, tastes
    again — they don't serve the dish after one attempt. The loop
    continues until the improvement between tastings becomes negligible.
    """

    def __init__(self, config: Optional[ConvergenceConfig] = None):
        self.config = config or ConvergenceConfig()

    def check_converged(self, scores: List[float]) -> bool:
        """Check if scores have converged (stabilized).

        Convergence = all pairwise deltas in the window are below threshold.
        """
        cfg = self.config
        if len(scores) < cfg.min_iterations:
            return False
        if len(scores) < cfg.score_history_window:
            return False

        window = scores[-cfg.score_history_window:]
        for i in range(1, len(window)):
            if abs(window[i] - window[i - 1]) >= cfg.stability_threshold:
                return False
        return True

    def check_improving(self, scores: List[float]) -> bool:
        """Check if recent iteration showed meaningful improvement."""
        if len(scores) < 2:
            return True  # too early to judge
        delta = scores[-1] - scores[-2]
        return delta > self.config.improvement_threshold

    async def run(
        self,
        artifact: Any,
        refiner: Refiner,
        evaluator: Evaluator,
        halt: Optional["AdaptiveHalt"] = None,
    ) -> ConvergenceResult:
        """Run the convergence loop.

        Args:
            artifact: Initial artifact to refine
            refiner: async (artifact, score, feedback_list) -> refined_artifact
            evaluator: async (artifact) -> (score, feedback)
            halt: Optional AdaptiveHalt for budget-aware stopping

        Returns:
            ConvergenceResult with final artifact and convergence info
        """
        cfg = self.config
        scores: List[float] = []
        feedback_history: List[str] = []
        current = artifact

        for iteration in range(cfg.max_iterations):
            # Evaluate current artifact
            score, feedback = await evaluator(current)
            scores.append(score)
            if feedback:
                feedback_history.append(feedback)

            # Check adaptive halt (budget-aware)
            if halt is not None:
                decision = halt.should_halt(
                    scores=scores,
                    budget_remaining=cfg.max_iterations - iteration - 1,
                    quality_target=1.0 - cfg.stability_threshold,
                )
                if decision.halt:
                    return ConvergenceResult(
                        converged=False,
                        final_artifact=current,
                        final_score=score,
                        iterations=iteration + 1,
                        score_history=tuple(scores),
                        reason=f"halted: {decision.reason}",
                    )

            # Check convergence
            if self.check_converged(scores):
                return ConvergenceResult(
                    converged=True,
                    final_artifact=current,
                    final_score=score,
                    iterations=iteration + 1,
                    score_history=tuple(scores),
                    reason="converged",
                )

            # Check if still improving (after min_iterations)
            if iteration >= cfg.min_iterations and not self.check_improving(scores):
                return ConvergenceResult(
                    converged=False,
                    final_artifact=current,
                    final_score=score,
                    iterations=iteration + 1,
                    score_history=tuple(scores),
                    reason="no_improvement",
                )

            # Refine if not the last iteration
            if iteration < cfg.max_iterations - 1:
                current = await refiner(current, score, feedback_history[-3:])

        return ConvergenceResult(
            converged=False,
            final_artifact=current,
            final_score=scores[-1] if scores else 0.0,
            iterations=cfg.max_iterations,
            score_history=tuple(scores),
            reason="max_iterations",
        )


# ================================================================
#  Adaptive Halt — budget-aware quality/cost tradeoff (HRM ACT)
# ================================================================

@dataclass(frozen=True)
class HaltDecision:
    """Decision from AdaptiveHalt."""
    halt: bool
    reason: str
    confidence: float  # 0-1, how confident we are in the halt decision


class AdaptiveHalt:
    """HRM ACT-inspired dynamic halt mechanism.

    Like a poker player deciding when to fold: considers current hand
    strength (quality), chips remaining (budget), and the pot odds
    (marginal improvement rate).

    Balances:
    - Quality target: have we reached "good enough"?
    - Budget: how many iterations remain?
    - Marginal returns: is each iteration adding meaningful value?
    """

    def __init__(
        self,
        quality_floor: float = 0.7,
        marginal_threshold: float = 0.02,
        budget_panic_ratio: float = 0.2,
    ):
        """
        Args:
            quality_floor: Score above this is acceptable to halt
            marginal_threshold: If avg improvement < this, halt
            budget_panic_ratio: If budget_remaining/total < this, halt if quality_floor met
        """
        self.quality_floor = quality_floor
        self.marginal_threshold = marginal_threshold
        self.budget_panic_ratio = budget_panic_ratio

    def should_halt(
        self,
        scores: List[float],
        budget_remaining: int,
        quality_target: float = 0.9,
    ) -> HaltDecision:
        """Decide whether to halt iteration.

        Args:
            scores: Score history so far
            budget_remaining: Iterations left in budget
            quality_target: Desired quality level

        Returns:
            HaltDecision with halt flag and reasoning
        """
        if not scores:
            return HaltDecision(halt=False, reason="no_scores", confidence=0.0)

        current_score = scores[-1]

        # 1. Quality target met
        if current_score >= quality_target:
            return HaltDecision(
                halt=True,
                reason=f"quality_target_met ({current_score:.3f} >= {quality_target:.3f})",
                confidence=0.95,
            )

        # 2. Budget panic: low budget + acceptable quality
        total_iterations = len(scores) + budget_remaining
        if total_iterations > 0:
            budget_ratio = budget_remaining / total_iterations
            if budget_ratio <= self.budget_panic_ratio and current_score >= self.quality_floor:
                return HaltDecision(
                    halt=True,
                    reason=f"budget_low ({budget_remaining} left, score {current_score:.3f} >= floor {self.quality_floor:.3f})",
                    confidence=0.8,
                )

        # 3. Diminishing returns
        if len(scores) >= 3:
            window = scores[-3:]
            recent_deltas = [window[i] - window[i - 1] for i in range(1, len(window))]
            avg_delta = sum(recent_deltas) / len(recent_deltas)
            if avg_delta < self.marginal_threshold and current_score >= self.quality_floor:
                return HaltDecision(
                    halt=True,
                    reason=f"diminishing_returns (avg_delta={avg_delta:.4f}, score={current_score:.3f})",
                    confidence=0.7,
                )

        return HaltDecision(halt=False, reason="continue", confidence=0.0)
