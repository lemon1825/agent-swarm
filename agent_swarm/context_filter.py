"""Context Isolation for Agent Swarm.

Inspired by Superpowers Subagent Context Isolation principle.
Limits context sent to agents based on configurable policies.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class ContextPolicy:
    """Policy controlling how much context an agent receives."""
    max_wave_history: int = 2  # max number of previous waves to include
    max_selective_items: int = 3  # max non-dependency items from context
    max_context_chars: int = 4000  # character budget for total context
    role_filter: Optional[List[str]] = None  # only include context from these roles
    include_own_history: bool = True  # include agent's own previous outputs
    exclude_patterns: List[str] = field(default_factory=list)  # patterns to strip from context

    # Default policies
    MINIMAL = None  # set below
    STANDARD = None
    FULL = None


# Set class-level presets after class definition
ContextPolicy.MINIMAL = ContextPolicy(max_wave_history=1, max_selective_items=1, max_context_chars=2000)
ContextPolicy.STANDARD = ContextPolicy(max_wave_history=2, max_selective_items=3, max_context_chars=4000)
ContextPolicy.FULL = ContextPolicy(max_wave_history=10, max_selective_items=10, max_context_chars=20000)


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
                    policy = ContextPolicy(**{
                        k: v for k, v in policy_data.items()
                        if hasattr(ContextPolicy, k)
                    })

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

        # 6. Enforce character budget via truncation
        filtered = _enforce_char_budget(filtered, char_budget)

        return filtered


def _get_role(item: Any) -> str:
    """Extract role from a context item."""
    if isinstance(item, dict):
        return item.get("role", "")
    if hasattr(item, "role"):
        return getattr(item, "role", "")
    return ""


def _apply_exclusions(data: Dict[str, Any], patterns: List[str]) -> Dict[str, Any]:
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
