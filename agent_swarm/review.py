"""Multi-Stage Review Pipeline for Agent Swarm.

Inspired by Superpowers 2-Stage Review + gstack CEO/Eng/Design 3-stage review.
Provides configurable multi-stage review with concurrent gate execution,
retry logic, skip conditions, and escalation support.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Awaitable, Tuple

from .convergence import ConvergenceConfig


__all__ = [
    "ReviewRole",
    "ReviewResult",
    "ReviewStage",
    "ReviewPipelineResult",
    "ReviewPipeline",
]


class ReviewRole(Enum):
    """Roles that can participate in a review stage."""
    SPEC_COMPLIANCE = "spec_compliance"
    CODE_QUALITY = "code_quality"
    SECURITY = "security"
    DESIGN = "design"
    CEO = "ceo"
    ENGINEERING = "engineering"


@dataclass(frozen=True)
class ReviewResult:
    """Result from a single reviewer gate."""
    role: ReviewRole
    passed: bool
    score: float  # 0.0 to 1.0
    feedback: str = ""
    issues: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ReviewStage:
    """A stage in the review pipeline containing one or more gates."""
    name: str
    gates: Tuple[ReviewRole, ...]  # roles that review in this stage
    pass_threshold: float = 0.7  # minimum average score to pass
    max_iterations: int = 3  # max retry attempts
    skip_condition: Optional[Callable[[Dict[str, Any]], bool]] = None
    require_all_pass: bool = False  # if True, ALL gates must pass individually
    convergence: Optional[ConvergenceConfig] = None  # HRM-style convergence-gated iteration


@dataclass
class ReviewPipelineResult:
    """Aggregate result from running the full pipeline."""
    passed: bool
    stages_completed: int
    stages_total: int
    stage_results: Dict[str, List[ReviewResult]] = field(default_factory=dict)
    escalated: bool = False
    escalation_reason: str = ""

    @property
    def overall_score(self) -> float:
        all_results = [r for results in self.stage_results.values() for r in results]
        if not all_results:
            return 0.0
        return sum(r.score for r in all_results) / len(all_results)


class ReviewPipeline:
    """Multi-stage review pipeline with concurrent gate execution.

    Stages run sequentially; gates within a stage run concurrently.
    Failed stages can be retried up to max_iterations times, and
    optionally escalated via an escalation callback.
    """

    def __init__(
        self,
        stages: List[ReviewStage],
        reviewers: Dict[ReviewRole, Callable[..., Awaitable[ReviewResult]]],
        escalation_callback: Optional[Callable[..., Awaitable[bool]]] = None,
    ):
        self.stages = stages
        self.reviewers = reviewers
        self.escalation_callback = escalation_callback

    async def run(
        self,
        run_id: str,
        proof: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> ReviewPipelineResult:
        """Execute all stages sequentially. Each stage can be skipped via skip_condition."""
        context = context or {}
        result = ReviewPipelineResult(
            passed=True,
            stages_completed=0,
            stages_total=len(self.stages),
        )

        for stage in self.stages:
            if stage.skip_condition and stage.skip_condition(context):
                result.stages_completed += 1
                continue

            stage_passed = False
            score_history: List[float] = []
            max_iter = stage.max_iterations
            for _iteration in range(max_iter):
                stage_results = await self._run_stage(stage, run_id, proof, context)
                result.stage_results[stage.name] = stage_results

                if self._stage_passes(stage, stage_results):
                    stage_passed = True
                    break

                # Track score for convergence check
                if stage_results:
                    avg = sum(r.score for r in stage_results) / len(stage_results)
                    score_history.append(avg)

                # HRM-style convergence: stop iterating if scores stabilized
                if stage.convergence and len(score_history) >= stage.convergence.min_iterations:
                    if self._check_converged(score_history, stage.convergence):
                        stage_passed = self._stage_passes(stage, stage_results)
                        break

                context[f"_feedback_{stage.name}"] = [
                    r.feedback for r in stage_results if r.feedback
                ]

            if not stage_passed:
                result.passed = False
                if self.escalation_callback:
                    escalated = await self.escalation_callback(
                        run_id, stage.name, result.stage_results.get(stage.name, [])
                    )
                    result.escalated = True
                    if escalated:
                        result.escalation_reason = (
                            f"Stage '{stage.name}' escalated and approved by human"
                        )
                        result.stages_completed += 1
                        continue
                    else:
                        result.escalation_reason = (
                            f"Stage '{stage.name}' escalated and rejected by human"
                        )
                        return result
                return result

            result.stages_completed += 1

        # If all stages completed (possibly via escalation), mark as passed
        if result.stages_completed == result.stages_total:
            result.passed = True

        return result

    async def _run_stage(
        self,
        stage: ReviewStage,
        run_id: str,
        proof: Any,
        context: Dict[str, Any],
    ) -> List[ReviewResult]:
        """Run all gates in a stage concurrently."""
        tasks = []
        for role in stage.gates:
            reviewer = self.reviewers.get(role)
            if reviewer:
                tasks.append(reviewer(run_id, proof, context))

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, ReviewResult)]

    @staticmethod
    def _check_converged(scores: List[float], config: ConvergenceConfig) -> bool:
        """Check if review scores have converged (HRM-style)."""
        if len(scores) < config.score_history_window:
            return False
        window = scores[-config.score_history_window:]
        return all(
            abs(window[i] - window[i - 1]) < config.stability_threshold
            for i in range(1, len(window))
        )

    def _stage_passes(self, stage: ReviewStage, results: List[ReviewResult]) -> bool:
        """Check whether a stage's results meet the pass criteria."""
        if not results:
            return True

        if stage.require_all_pass:
            return all(r.passed for r in results)

        avg_score = sum(r.score for r in results) / len(results)
        return avg_score >= stage.pass_threshold
