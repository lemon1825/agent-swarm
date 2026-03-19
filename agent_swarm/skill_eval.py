"""Skill Evaluator — measure skill effectiveness with A/B testing.

Based on SkillsBench (Li et al., 2026, arXiv:2602.12670) findings:
- Curated skills improve pass rate by +16.2pp on average
- 16/84 tasks show negative delta (skills hurt performance)
- 2-3 module focused skills outperform comprehensive documentation
- Self-generated skills provide no benefit on average

Usage:
    from agent_swarm.skill_eval import SkillEvaluator

    evaluator = SkillEvaluator(swarm)
    report = await evaluator.evaluate(goal, tasks, runs=5)
    print(report.summary())

    # Auto-evaluate mode on SkillBank
    bank = SkillBank(auto_evaluate=True, eval_interval=50)
"""

__all__ = [
    'SkillEvaluator', 'SkillEvalReport', 'SkillDelta',
    'evaluate_skill_focus', 'FOCUS_THRESHOLD',
]

import asyncio
import copy
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


FOCUS_THRESHOLD = 3  # SkillsBench: 2-3 modules optimal


@dataclass
class SkillDelta:
    """Result of A/B testing a single skill."""
    skill_name: str
    with_skill_pass_rate: float      # 0.0 ~ 1.0
    without_skill_pass_rate: float   # 0.0 ~ 1.0
    delta_pp: float                  # percentage points
    runs_with: int = 0
    runs_without: int = 0
    avg_tokens_with: float = 0
    avg_tokens_without: float = 0
    recommendation: str = ""         # "keep", "disable", "needs_more_data"

    @property
    def is_harmful(self) -> bool:
        return self.delta_pp < -2.0 and self.runs_with >= 3

    @property
    def is_beneficial(self) -> bool:
        return self.delta_pp > 2.0 and self.runs_with >= 3

    def summary_line(self) -> str:
        symbol = "✓" if self.is_beneficial else ("✗" if self.is_harmful else "~")
        return (
            f"  {symbol} {self.skill_name}: "
            f"{self.with_skill_pass_rate:.0%} vs {self.without_skill_pass_rate:.0%} "
            f"(delta: {self.delta_pp:+.1f}pp) → {self.recommendation}"
        )


@dataclass
class SkillEvalReport:
    """Full evaluation report for all skills."""
    goal: str
    deltas: List[SkillDelta] = field(default_factory=list)
    total_runs: int = 0
    eval_time_s: float = 0
    timestamp: float = field(default_factory=time.time)

    @property
    def beneficial_skills(self) -> List[SkillDelta]:
        return [d for d in self.deltas if d.is_beneficial]

    @property
    def harmful_skills(self) -> List[SkillDelta]:
        return [d for d in self.deltas if d.is_harmful]

    @property
    def neutral_skills(self) -> List[SkillDelta]:
        return [d for d in self.deltas if not d.is_beneficial and not d.is_harmful]

    def summary(self) -> str:
        lines = [
            f"Skill Evaluation Report",
            f"Goal: {self.goal}",
            f"Total runs: {self.total_runs} | Time: {self.eval_time_s:.1f}s",
            f"",
            f"Beneficial ({len(self.beneficial_skills)}):",
        ]
        for d in self.beneficial_skills:
            lines.append(d.summary_line())

        lines.append(f"")
        lines.append(f"Harmful ({len(self.harmful_skills)}):")
        for d in self.harmful_skills:
            lines.append(d.summary_line())

        lines.append(f"")
        lines.append(f"Neutral ({len(self.neutral_skills)}):")
        for d in self.neutral_skills:
            lines.append(d.summary_line())

        return "\n".join(lines)


class SkillEvaluator:
    """A/B test skills to measure their effectiveness.

    Args:
        swarm: Swarm instance to run evaluations
        success_fn: Optional function to judge if a run succeeded.
                    Default: all tasks succeeded.
                    Signature: (result_dict) -> bool
    """

    def __init__(self, swarm, success_fn: Callable = None):
        self._swarm = swarm
        self._success_fn = success_fn or self._default_success

    async def evaluate(self, goal: str, tasks: list,
                       runs: int = 5, skills_to_test: list = None) -> SkillEvalReport:
        """Run A/B test for each skill.

        For each skill:
          - Run N times WITH the skill active
          - Run N times WITHOUT the skill (disabled)
          - Compare pass rates

        Args:
            goal: Goal string for the run
            tasks: Task list for the run
            runs: Number of runs per condition (default 5)
            skills_to_test: Optional list of skill names to test.
                           If None, tests all skills in the bank.

        Returns:
            SkillEvalReport with per-skill deltas
        """
        start = time.time()
        bank = self._swarm.skill_bank
        if bank is None:
            return SkillEvalReport(goal=goal)

        all_skills = bank._all()
        if skills_to_test:
            all_skills = [s for s in all_skills if s.name in skills_to_test]

        deltas = []
        total_runs = 0

        for skill in all_skills:
            # A: With skill (normal)
            with_results = []
            for _ in range(runs):
                try:
                    result = await self._swarm.run(goal, tasks=self._copy_tasks(tasks))
                    with_results.append(result)
                except Exception:
                    with_results.append(None)
                total_runs += 1

            # B: Without this skill (temporarily remove)
            original_state = skill.state
            skill.state = type(skill.state)("inactive") if hasattr(skill.state, "value") else "inactive"

            without_results = []
            for _ in range(runs):
                try:
                    result = await self._swarm.run(goal, tasks=self._copy_tasks(tasks))
                    without_results.append(result)
                except Exception:
                    without_results.append(None)
                total_runs += 1

            # Restore skill
            skill.state = original_state

            # Calculate delta
            with_pass = sum(1 for r in with_results if r and self._success_fn(r)) / max(len(with_results), 1)
            without_pass = sum(1 for r in without_results if r and self._success_fn(r)) / max(len(without_results), 1)
            delta_pp = (with_pass - without_pass) * 100

            with_tokens = [r["metadata"].get("total_tokens", 0) for r in with_results if r]
            without_tokens = [r["metadata"].get("total_tokens", 0) for r in without_results if r]

            recommendation = "keep" if delta_pp > 2 else ("disable" if delta_pp < -2 else "neutral")

            deltas.append(SkillDelta(
                skill_name=skill.name,
                with_skill_pass_rate=with_pass,
                without_skill_pass_rate=without_pass,
                delta_pp=delta_pp,
                runs_with=len(with_results),
                runs_without=len(without_results),
                avg_tokens_with=sum(with_tokens) / max(len(with_tokens), 1),
                avg_tokens_without=sum(without_tokens) / max(len(without_tokens), 1),
                recommendation=recommendation,
            ))

        return SkillEvalReport(
            goal=goal,
            deltas=deltas,
            total_runs=total_runs,
            eval_time_s=time.time() - start,
        )

    async def quick_check(self, goal: str, tasks: list, skill_name: str) -> SkillDelta:
        """Quick check a single skill with 3 runs each."""
        report = await self.evaluate(goal, tasks, runs=3, skills_to_test=[skill_name])
        if report.deltas:
            return report.deltas[0]
        return SkillDelta(skill_name=skill_name, with_skill_pass_rate=0,
                          without_skill_pass_rate=0, delta_pp=0, recommendation="no_data")

    def _copy_tasks(self, tasks):
        """Deep copy tasks to avoid state bleeding between runs."""
        return [copy.deepcopy(t) for t in tasks]

    @staticmethod
    def _default_success(result: dict) -> bool:
        meta = result.get("metadata", {})
        return meta.get("succeeded", 0) == meta.get("total_tasks", 0) and meta.get("total_tasks", 0) > 0


def evaluate_skill_focus(skill) -> dict:
    """Evaluate a skill's focus level based on SkillsBench findings.

    SkillsBench: 2-3 module focused skills outperform comprehensive documentation.

    Returns:
        {
            "module_count": int,
            "is_focused": bool,
            "recommendation": str,
            "focus_score": float,  # 0.0 (too broad) to 1.0 (well focused)
        }
    """
    # Count modules/components in the skill
    module_count = 0
    principle = getattr(skill, "principle", "") or ""
    when = getattr(skill, "when_to_apply", "") or ""
    text = principle + " " + when

    # Heuristic: count distinct capability areas
    separators = [",", ";", "\n", " and ", " + ", "|"]
    parts = [text]
    for sep in separators:
        new_parts = []
        for p in parts:
            new_parts.extend(p.split(sep))
        parts = new_parts
    module_count = len([p for p in parts if p.strip() and len(p.strip()) > 3])
    module_count = max(module_count, 1)

    # Check manifest modules if available
    manifest = getattr(skill, "manifest", None)
    if manifest:
        caps = getattr(manifest, "capabilities", []) or []
        task_types = getattr(manifest, "task_types", []) or []
        module_count = max(len(caps) + len(task_types), module_count)

    is_focused = module_count <= FOCUS_THRESHOLD
    focus_score = min(1.0, FOCUS_THRESHOLD / max(module_count, 1))

    if module_count <= FOCUS_THRESHOLD:
        recommendation = f"Good: {module_count} modules (optimal range 2-3)"
    elif module_count <= 5:
        recommendation = f"Consider splitting: {module_count} modules (SkillsBench optimal: 2-3)"
    else:
        recommendation = f"Too broad: {module_count} modules. Split into {module_count // 2}-{module_count // 3 + 1} focused skills"

    return {
        "module_count": module_count,
        "is_focused": is_focused,
        "recommendation": recommendation,
        "focus_score": focus_score,
    }
