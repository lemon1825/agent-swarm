"""Smart Model Router — auto-select LLM model based on task complexity.

Zero dependencies. Works with any LLM that accepts a model parameter.

Usage:
    from agent_swarm.router import SmartRouter

    router = SmartRouter({
        "fast": my_mini_llm,       # GPT-4o-mini, Claude Haiku — cheap, fast
        "balanced": my_main_llm,    # GPT-4o, Claude Sonnet — good balance
        "strong": my_strong_llm,    # GPT-4, Claude Opus — expensive, best quality
    })

    swarm = Swarm(llm=router.route)
"""

__all__ = ['_STRONG_SIGNALS', '_FAST_SIGNALS', 'SmartRouter']
from typing import Any, Callable, Dict, Optional


# Task complexity signals
_STRONG_SIGNALS = {
    "analyze", "architecture", "design", "strategy", "complex",
    "security", "audit", "compliance", "critical", "risk",
    "synthesize", "compare", "evaluate", "decision", "trade-off",
    "refactor", "migrate", "review entire", "full analysis",
}

_FAST_SIGNALS = {
    "format", "convert", "extract", "list", "summarize briefly",
    "translate", "count", "check", "validate", "verify format",
    "simple", "quick", "basic", "short",
}


class SmartRouter:
    """Routes prompts to appropriate LLM based on task complexity.

    Tiers:
        fast     — simple tasks (formatting, extraction, validation)
        balanced — standard tasks (writing, research, analysis)
        strong   — complex tasks (architecture, security audit, strategy)
    """

    def __init__(self, llms: Dict[str, Callable], default_tier: str = "balanced"):
        self.llms = llms
        self.default_tier = default_tier
        self.route_history: list = []

    def _classify(self, prompt: str) -> str:
        """Classify prompt complexity → tier name."""
        p_lower = prompt.lower()
        prompt_len = len(prompt)

        # Strong signals
        strong_score = sum(1 for s in _STRONG_SIGNALS if s in p_lower)
        fast_score = sum(1 for s in _FAST_SIGNALS if s in p_lower)

        # Length heuristic: very long prompts usually need stronger models
        if prompt_len > 8000: strong_score += 2
        elif prompt_len < 500: fast_score += 1

        # Role-based hints
        if any(r in p_lower for r in ("reviewer", "approver", "lead", "senior", "architect")):
            strong_score += 1
        if any(r in p_lower for r in ("assistant", "helper", "formatter")):
            fast_score += 1

        # Retry hint present = previous failure = need stronger model
        if "[previous attempt failed]" in p_lower:
            strong_score += 1

        if strong_score > fast_score and strong_score >= 2:
            return "strong"
        if fast_score > strong_score and fast_score >= 2:
            return "fast"
        return "balanced"

    async def route(self, prompt: str, tools=None):
        """Route prompt to appropriate LLM. Use as: Swarm(llm=router.route)"""
        tier = self._classify(prompt)

        # Fallback chain: requested tier → balanced → any available
        llm = self.llms.get(tier) or self.llms.get(self.default_tier) or next(iter(self.llms.values()))

        self.route_history.append({"tier": tier, "prompt_len": len(prompt)})
        if len(self.route_history) > 200:
            self.route_history = self.route_history[-200:]

        return await llm(prompt, tools)

    def stats(self) -> Dict:
        """Routing statistics."""
        if not self.route_history:
            return {"total": 0, "fast": 0, "balanced": 0, "strong": 0}
        total = len(self.route_history)
        by_tier = {}
        for r in self.route_history:
            by_tier[r["tier"]] = by_tier.get(r["tier"], 0) + 1
        return {
            "total": total,
            "fast": by_tier.get("fast", 0),
            "balanced": by_tier.get("balanced", 0),
            "strong": by_tier.get("strong", 0),
            "fast_pct": round(by_tier.get("fast", 0) / total * 100),
            "strong_pct": round(by_tier.get("strong", 0) / total * 100),
        }
