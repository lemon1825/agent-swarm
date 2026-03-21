"""Context Isolation for Agent Swarm.

Limits context sent to agents based on configurable policies.

Extended with XSA (Exclusive Self Attention, Zhai 2026, arXiv:2603.09078):
- exclude_self: Remove agent's own output from context (orthogonal projection)
- orthogonal_project(): TF-IDF vector-based self-component removal
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple


__all__ = [
    "ContextPolicy",
    "ContextFilter",
    "orthogonal_project",
]


@dataclass(frozen=True)
class ContextPolicy:
    """Policy controlling how much context an agent receives."""
    max_wave_history: int = 2  # max number of previous waves to include
    max_selective_items: int = 3  # max non-dependency items from context
    max_context_chars: int = 4000  # character budget for total context
    role_filter: Optional[Tuple[str, ...]] = None  # only include context from these roles
    include_own_history: bool = True  # include agent's own previous outputs
    exclude_patterns: Tuple[str, ...] = ()  # patterns to strip from context
    exclude_self: bool = False  # XSA: exclude agent's own output from context
    orthogonal_strength: float = 1.0  # 0.0 = no projection, 1.0 = full XSA exclusion


# Module-level preset constants (frozen instances)
POLICY_MINIMAL = ContextPolicy(max_wave_history=1, max_selective_items=1, max_context_chars=2000)
POLICY_STANDARD = ContextPolicy(max_wave_history=2, max_selective_items=3, max_context_chars=4000)
POLICY_FULL = ContextPolicy(max_wave_history=10, max_selective_items=10, max_context_chars=20000)
POLICY_XSA = ContextPolicy(
    max_wave_history=2, max_selective_items=5, max_context_chars=8000,
    exclude_self=True, orthogonal_strength=1.0,
)

# Class-level aliases for backward compatibility (read-only references)
ContextPolicy.MINIMAL = POLICY_MINIMAL  # type: ignore[attr-defined]
ContextPolicy.STANDARD = POLICY_STANDARD  # type: ignore[attr-defined]
ContextPolicy.FULL = POLICY_FULL  # type: ignore[attr-defined]
ContextPolicy.XSA = POLICY_XSA  # type: ignore[attr-defined]


# ================================================================
#  XSA: Orthogonal Projection (software analog of Exclusive Self Attention)
# ================================================================

def _tokenize(text: str) -> List[str]:
    """Simple word tokenization for TF-IDF."""
    return [w.lower() for w in re.findall(r'\b\w{3,}\b', text)]


def _tf_vector(tokens: List[str]) -> Dict[str, float]:
    """Term frequency vector."""
    if not tokens:
        return {}
    counts = Counter(tokens)
    total = len(tokens)
    return {term: count / total for term, count in counts.items()}


def _cosine_similarity(a: Dict[str, float], b: Dict[str, float]) -> float:
    """Cosine similarity between two sparse vectors."""
    if not a or not b:
        return 0.0
    common = set(a.keys()) & set(b.keys())
    if not common:
        return 0.0
    dot = sum(a[k] * b[k] for k in common)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a < 1e-10 or norm_b < 1e-10:
        return 0.0
    return dot / (norm_a * norm_b)


def orthogonal_project(
    context_text: str,
    self_text: str,
    strength: float = 1.0,
) -> Tuple[str, float]:
    """Remove self-similar content from context (XSA orthogonal projection).

    Like noise-canceling headphones for self-reference: identifies the
    "frequency" of an agent's own voice in the context and subtracts it,
    leaving only the signal from other agents.

    Args:
        context_text: The full context being sent to the agent
        self_text: The agent's own previous output
        strength: 0.0 = no removal, 1.0 = full removal

    Returns:
        (filtered_text, similarity_score): Context with self-similar
        sentences removed, and the measured self-similarity.
    """
    if not context_text or not self_text or strength <= 0:
        return context_text, 0.0

    self_tokens = _tokenize(self_text)
    self_tf = _tf_vector(self_tokens)
    if not self_tf:
        return context_text, 0.0

    # Split context into sentences and filter
    sentences = re.split(r'(?<=[.!?])\s+', context_text)
    if not sentences:
        return context_text, 0.0

    kept = []
    removed_count = 0
    threshold = 0.5 * strength  # higher strength = more aggressive filtering

    for sentence in sentences:
        sent_tokens = _tokenize(sentence)
        sent_tf = _tf_vector(sent_tokens)
        sim = _cosine_similarity(sent_tf, self_tf)

        if sim < threshold:
            kept.append(sentence)
        else:
            removed_count += 1

    overall_sim = removed_count / max(len(sentences), 1)
    return " ".join(kept), overall_sim


# ================================================================
#  ContextFilter
# ================================================================

class ContextFilter:
    """Filters and trims context based on a ContextPolicy."""

    @staticmethod
    def filter(
        task: Any,  # SubTask - using Any to avoid circular imports
        context: Dict[str, Any],
        policy: Optional[ContextPolicy] = None,
    ) -> Dict[str, Any]:
        """Filter context according to policy. Returns new dict (no mutation)."""
        if policy is None:
            # Check task metadata for policy override
            if hasattr(task, 'metadata') and task.metadata:
                policy_data = task.metadata.get("context_policy")
                if isinstance(policy_data, ContextPolicy):
                    policy = policy_data
                elif isinstance(policy_data, dict):
                    cleaned = {}
                    for k, v in policy_data.items():
                        if not hasattr(ContextPolicy, k):
                            continue
                        # Convert lists to tuples for frozen dataclass
                        if k in ("role_filter", "exclude_patterns") and isinstance(v, list):
                            cleaned[k] = tuple(v)
                        else:
                            cleaned[k] = v
                    policy = ContextPolicy(**cleaned)

            if policy is None:
                return context  # no filtering

        filtered = {}
        char_budget = policy.max_context_chars

        # 1. Filter wave history
        if "wave_history" in context:
            waves = context["wave_history"]
            if isinstance(waves, list):
                filtered["wave_history"] = waves[-policy.max_wave_history:]
            elif isinstance(waves, dict):
                sorted_keys = sorted(waves.keys())[-policy.max_wave_history:]
                filtered["wave_history"] = {k: waves[k] for k in sorted_keys}

        # 2. Filter selective items (non-dependency context)
        if "selective_context" in context:
            items = context["selective_context"]
            if isinstance(items, list):
                # Apply role filter if set
                if policy.role_filter:
                    items = [i for i in items if _get_role(i) in policy.role_filter]
                filtered["selective_context"] = items[:policy.max_selective_items]

        # 3. Pass through dependency context (always included, not filtered)
        if "dep_context" in context:
            filtered["dep_context"] = context["dep_context"]

        # 4. Copy other keys that aren't filtered
        for key in context:
            if key not in filtered:
                filtered[key] = context[key]

        # 5. Apply exclude patterns
        if policy.exclude_patterns:
            filtered = _apply_exclusions(filtered, policy.exclude_patterns)

        # 6. XSA: Exclude self-context via orthogonal projection
        if policy.exclude_self:
            filtered = _apply_xsa_exclusion(
                filtered, task, policy.orthogonal_strength
            )

        # 7. Enforce character budget via truncation
        filtered = _enforce_char_budget(filtered, char_budget)

        return filtered


def _get_role(item: Any) -> str:
    """Extract role from a context item."""
    if isinstance(item, dict):
        return item.get("role", "")
    if hasattr(item, "role"):
        return getattr(item, "role", "")
    return ""


def _get_task_id(task: Any) -> str:
    """Extract task ID from a task object."""
    if isinstance(task, dict):
        return task.get("id", "")
    if hasattr(task, "id"):
        return getattr(task, "id", "")
    return ""


def _apply_xsa_exclusion(
    data: Dict[str, Any],
    task: Any,
    strength: float,
) -> Dict[str, Any]:
    """Apply XSA-style self-context exclusion.

    Removes content that is too similar to the current agent's own
    previous outputs from the context dictionary.
    """
    task_id = _get_task_id(task)
    if not task_id:
        return data

    # Find self-output in context
    self_output = ""
    dep_ctx = data.get("dep_context", {})
    if isinstance(dep_ctx, dict) and task_id in dep_ctx:
        self_output = str(dep_ctx[task_id])

    if not self_output:
        return data

    result = {}
    for key, value in data.items():
        if key == "dep_context" and isinstance(value, dict):
            # Remove self from dependency context
            result[key] = {k: v for k, v in value.items() if k != task_id}
        elif isinstance(value, str) and len(value) > 20:
            projected, _ = orthogonal_project(value, self_output, strength)
            result[key] = projected
        else:
            result[key] = value
    return result


def _apply_exclusions(data: Dict[str, Any], patterns: Sequence[str]) -> Dict[str, Any]:
    """Remove values matching exclusion patterns (simple substring match)."""
    result = {}
    for key, value in data.items():
        if isinstance(value, str):
            clean = value
            for pattern in patterns:
                clean = clean.replace(pattern, "[FILTERED]")
            result[key] = clean
        else:
            result[key] = value
    return result


def _enforce_char_budget(data: Dict[str, Any], budget: int) -> Dict[str, Any]:
    """Truncate string values to fit within character budget."""
    total = 0
    result = {}
    for key, value in data.items():
        if isinstance(value, str):
            remaining = max(0, budget - total)
            if remaining == 0:
                result[key] = ""
            elif len(value) > remaining:
                result[key] = value[:remaining] + "...[truncated]"
                total += remaining
            else:
                result[key] = value
                total += len(value)
        else:
            result[key] = value
            # Estimate non-string size
            total += len(str(value))
    return result
