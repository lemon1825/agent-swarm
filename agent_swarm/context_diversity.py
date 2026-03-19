"""Context Diversity — reduce self-reference bias in agent outputs.

Inspired by Exclusive Self Attention (Zhai, 2026, arXiv:2603.09078):
- SA output has high cosine similarity with self value vector (attention similarity bias)
- Excluding self-position information improves context modeling
- Division of labor: context aggregation vs point-wise feature transformation

Applied to agent workflows:
- Agents tend to repeat/echo their own previous output (self-reference bias)
- Better results when agents focus on OTHER agents' outputs
- Context diversity score measures how much an agent leveraged cross-agent info

Usage:
    from agent_swarm.context_diversity import (
        ContextDiversityScorer,
        exclude_self_context,
        diversity_report,
    )

    # Score a completed run
    scorer = ContextDiversityScorer()
    report = scorer.score(result)
    print(report)

    # Exclude self-context in prompt building
    prompt = exclude_self_context(
        base_prompt="Analyze the data",
        agent_outputs={"researcher": "...", "analyst": "..."},
        current_agent="analyst",
    )
"""

__all__ = [
    'ContextDiversityScorer', 'DiversityReport', 'AgentDiversityScore',
    'exclude_self_context', 'diversity_report',
]

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class AgentDiversityScore:
    """Diversity score for a single agent's output."""
    task_id: str
    role: str
    self_reference_ratio: float    # 0.0 (no self-ref) to 1.0 (all self-ref)
    cross_reference_count: int     # number of other agents' outputs referenced
    unique_terms_ratio: float      # ratio of unique terms not from dependencies
    diversity_score: float         # 0.0 (pure echo) to 1.0 (fully diverse)
    referenced_tasks: List[str] = field(default_factory=list)  # which tasks were referenced
    recommendation: str = ""

    def summary_line(self) -> str:
        symbol = "✓" if self.diversity_score > 0.6 else ("⚠" if self.diversity_score > 0.3 else "✗")
        return (
            f"  {symbol} [{self.task_id}] ({self.role}) "
            f"diversity={self.diversity_score:.2f} "
            f"self_ref={self.self_reference_ratio:.0%} "
            f"cross_ref={self.cross_reference_count} "
            f"→ {self.recommendation}"
        )


@dataclass
class DiversityReport:
    """Diversity report for an entire run."""
    avg_diversity: float = 0.0
    avg_self_reference: float = 0.0
    agent_scores: List[AgentDiversityScore] = field(default_factory=list)
    high_self_ref_agents: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "Context Diversity Report",
            f"  Average diversity: {self.avg_diversity:.2f}",
            f"  Average self-reference: {self.avg_self_reference:.0%}",
            f"  High self-ref agents: {', '.join(self.high_self_ref_agents) or 'none'}",
            "",
            "Per-agent scores:",
        ]
        for s in self.agent_scores:
            lines.append(s.summary_line())

        if self.recommendations:
            lines.append("")
            lines.append("Recommendations:")
            for r in self.recommendations:
                lines.append(f"  • {r}")

        return "\n".join(lines)


class ContextDiversityScorer:
    """Score how well agents leverage cross-agent context vs echoing themselves.

    Based on XSA insight: excluding self-position information
    improves context modeling quality.
    """

    def __init__(self, self_ref_threshold: float = 0.5):
        """
        Args:
            self_ref_threshold: Above this ratio, agent is flagged for high self-reference
        """
        self.self_ref_threshold = self_ref_threshold

    def score(self, result: dict) -> DiversityReport:
        """Score a completed Swarm.run() result.

        Args:
            result: Output from Swarm.run()

        Returns:
            DiversityReport with per-agent and aggregate scores
        """
        results = result.get("results", {})
        if not results:
            return DiversityReport()

        # Build output map: task_id → output text
        output_map = {}
        dep_map = {}
        for tid, r in results.items():
            output_map[tid] = r.output or "" if r.success else ""
            dep_map[tid] = []  # TaskResult has no dependencies field

        # Score each agent
        agent_scores = []
        for tid, r in results.items():
            if not r.success or not r.output:
                continue

            output = r.output
            deps = dep_map.get(tid, [])

            # Calculate self-reference ratio
            self_ref = self._self_reference_ratio(output, output_map, tid)

            # Calculate cross-reference count
            cross_refs = self._cross_references(output, output_map, tid)

            # Calculate unique terms ratio
            unique_ratio = self._unique_terms_ratio(output, output_map, tid, deps)

            # Combined diversity score
            diversity = (
                (1.0 - self_ref) * 0.4 +          # low self-ref is good
                min(len(cross_refs) / max(len(deps), 1), 1.0) * 0.3 +  # referencing deps is good
                unique_ratio * 0.3                  # unique content is good
            )

            recommendation = self._recommend(self_ref, len(cross_refs), unique_ratio, diversity)

            agent_scores.append(AgentDiversityScore(
                task_id=tid,
                role=getattr(r, "role", ""),
                self_reference_ratio=self_ref,
                cross_reference_count=len(cross_refs),
                unique_terms_ratio=unique_ratio,
                diversity_score=diversity,
                referenced_tasks=cross_refs,
                recommendation=recommendation,
            ))

        # Aggregate
        avg_diversity = sum(s.diversity_score for s in agent_scores) / max(len(agent_scores), 1)
        avg_self_ref = sum(s.self_reference_ratio for s in agent_scores) / max(len(agent_scores), 1)
        high_self = [s.task_id for s in agent_scores if s.self_reference_ratio > self.self_ref_threshold]

        recommendations = []
        if avg_self_ref > 0.5:
            recommendations.append(
                "High average self-reference. Consider using exclude_self_context() "
                "to reduce echo effect in prompts."
            )
        if avg_diversity < 0.4:
            recommendations.append(
                "Low context diversity. Agents may not be leveraging each other's outputs. "
                "Check task dependencies and prompt structure."
            )
        for s in agent_scores:
            if s.self_reference_ratio > 0.7:
                recommendations.append(
                    f"Agent [{s.task_id}] has {s.self_reference_ratio:.0%} self-reference. "
                    f"Its output largely echoes its input rather than synthesizing context."
                )

        return DiversityReport(
            avg_diversity=avg_diversity,
            avg_self_reference=avg_self_ref,
            agent_scores=agent_scores,
            high_self_ref_agents=high_self,
            recommendations=recommendations,
        )

    def _self_reference_ratio(self, output: str, output_map: dict, current_tid: str) -> float:
        """Measure how much output overlaps with the agent's own prompt/input."""
        if not output:
            return 0.0

        output_words = set(self._tokenize(output))
        if not output_words:
            return 0.0

        # Compare against what was likely in the agent's own prompt
        # (approximated by the task description embedded in other outputs)
        own_words = set()
        for tid, text in output_map.items():
            if tid == current_tid and text:
                own_words.update(self._tokenize(text))

        if not own_words:
            return 0.0

        overlap = output_words & own_words
        return len(overlap) / max(len(output_words), 1)

    def _cross_references(self, output: str, output_map: dict, current_tid: str) -> List[str]:
        """Find which other agents' outputs are reflected in this output."""
        referenced = []
        output_lower = output.lower()

        for tid, text in output_map.items():
            if tid == current_tid or not text:
                continue

            # Check if significant phrases from other outputs appear
            other_phrases = self._extract_key_phrases(text)
            matches = sum(1 for p in other_phrases if p.lower() in output_lower)
            if matches >= 2 or (matches >= 1 and len(other_phrases) <= 3):
                referenced.append(tid)

        return referenced

    def _unique_terms_ratio(self, output: str, output_map: dict,
                            current_tid: str, deps: list) -> float:
        """Ratio of terms in output that don't come from dependency outputs."""
        output_words = set(self._tokenize(output))
        if not output_words:
            return 0.0

        dep_words = set()
        for dep_id in deps:
            if dep_id in output_map and output_map[dep_id]:
                dep_words.update(self._tokenize(output_map[dep_id]))

        if not dep_words:
            return 1.0  # No deps → everything is unique

        unique = output_words - dep_words
        return len(unique) / max(len(output_words), 1)

    def _recommend(self, self_ref: float, cross_count: int,
                   unique_ratio: float, diversity: float) -> str:
        if diversity > 0.7:
            return "Good diversity"
        if self_ref > 0.6:
            return "High self-reference — add exclude_self_context()"
        if cross_count == 0:
            return "No cross-references — check dependencies"
        if unique_ratio < 0.3:
            return "Low unique content — agent is mostly echoing inputs"
        return "Acceptable"

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Simple word tokenization."""
        return [w.lower() for w in re.findall(r'\b\w{3,}\b', text)]

    @staticmethod
    def _extract_key_phrases(text: str, max_phrases: int = 10) -> List[str]:
        """Extract key phrases (2-3 word sequences) from text."""
        words = re.findall(r'\b\w{3,}\b', text.lower())
        phrases = []
        for i in range(len(words) - 1):
            phrases.append(f"{words[i]} {words[i+1]}")
        # Take most distinctive (longer words)
        phrases.sort(key=lambda p: -len(p))
        return phrases[:max_phrases]


def exclude_self_context(base_prompt: str, agent_outputs: Dict[str, str],
                         current_agent: str, weight_others: float = 1.5) -> str:
    """Build a prompt that de-emphasizes self-reference and emphasizes cross-agent context.

    Inspired by XSA: exclude self-position information to improve context modeling.

    Args:
        base_prompt: The base task prompt
        agent_outputs: Dict of {agent_id: output_text} from previous agents
        current_agent: ID of the current agent (to exclude)
        weight_others: Multiplier for emphasis on other agents' outputs

    Returns:
        Modified prompt with cross-context emphasis
    """
    # Separate self and other outputs
    other_outputs = {k: v for k, v in agent_outputs.items() if k != current_agent}
    self_output = agent_outputs.get(current_agent, "")

    if not other_outputs:
        return base_prompt

    # Build context section emphasizing others
    context_parts = []
    for agent_id, output in other_outputs.items():
        if output:
            context_parts.append(f"[From {agent_id}]: {output}")

    cross_context = "\n\n".join(context_parts)

    # Build final prompt
    prompt = f"""{base_prompt}

IMPORTANT CONTEXT FROM OTHER AGENTS (use this as your primary input):
{cross_context}

INSTRUCTION: Focus on synthesizing and building upon the above context from other agents.
Avoid simply repeating what was already said. Add new insights, analysis, or perspective."""

    return prompt


def diversity_report(result: dict) -> DiversityReport:
    """Convenience function to generate diversity report from a run result."""
    return ContextDiversityScorer().score(result)
