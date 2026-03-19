"""Tests for router.py — SmartRouter, classification logic."""
import asyncio
import pytest
from agent_swarm.router import SmartRouter, _STRONG_SIGNALS, _FAST_SIGNALS


# ── _classify ──

def test_classify_strong_signals():
    router = SmartRouter({"strong": None, "balanced": None, "fast": None})
    assert router._classify("analyze the architecture and design a security strategy") == "strong"


def test_classify_fast_signals():
    router = SmartRouter({"strong": None, "balanced": None, "fast": None})
    assert router._classify("format and convert this simple list") == "fast"


def test_classify_balanced_default():
    router = SmartRouter({"strong": None, "balanced": None, "fast": None})
    assert router._classify("Write a paragraph about the project") == "balanced"


def test_classify_length_heuristic_long():
    router = SmartRouter({"strong": None, "balanced": None, "fast": None})
    long_prompt = "analyze " + "x " * 5000
    assert router._classify(long_prompt) == "strong"


def test_classify_length_heuristic_short():
    router = SmartRouter({"strong": None, "balanced": None, "fast": None})
    assert router._classify("check format") == "fast"


def test_classify_role_hints_strong():
    router = SmartRouter({"strong": None, "balanced": None, "fast": None})
    assert router._classify("As a senior architect, analyze and design the system") == "strong"


def test_classify_role_hints_fast():
    router = SmartRouter({"strong": None, "balanced": None, "fast": None})
    assert router._classify("As a formatter assistant, convert this simple text") == "fast"


def test_classify_retry_boost():
    router = SmartRouter({"strong": None, "balanced": None, "fast": None})
    prompt = "[previous attempt failed] analyze this code"
    assert router._classify(prompt) == "strong"


# ── route() ──

def test_route_calls_correct_tier():
    calls = {"tier": None}

    async def fast_llm(prompt, tools=None):
        calls["tier"] = "fast"
        return "fast result"

    async def balanced_llm(prompt, tools=None):
        calls["tier"] = "balanced"
        return "balanced result"

    router = SmartRouter({"fast": fast_llm, "balanced": balanced_llm})
    result = asyncio.run(router.route("Write about something"))
    assert calls["tier"] == "balanced"
    assert result == "balanced result"


def test_route_fallback_chain():
    async def balanced_llm(prompt, tools=None):
        return "ok"

    router = SmartRouter({"balanced": balanced_llm})
    result = asyncio.run(router.route("analyze the architecture and design a security strategy"))
    assert result == "ok"


def test_route_records_history():
    async def llm(prompt, tools=None):
        return "ok"

    router = SmartRouter({"balanced": llm, "fast": llm})

    async def run():
        await router.route("hello world")
    asyncio.run(run())
    assert len(router.route_history) == 1
    assert "tier" in router.route_history[0]


def test_route_history_capped():
    async def llm(prompt, tools=None):
        return "ok"

    router = SmartRouter({"balanced": llm})

    async def run():
        for i in range(250):
            await router.route(f"prompt {i}")
    asyncio.run(run())
    assert len(router.route_history) == 200


# ── stats() ──

def test_stats_empty():
    router = SmartRouter({"balanced": None})
    s = router.stats()
    assert s["total"] == 0


def test_stats_after_routes():
    async def llm(prompt, tools=None):
        return "ok"

    router = SmartRouter({"balanced": llm, "fast": llm, "strong": llm})

    async def run():
        await router.route("simple check format")
        await router.route("write about topic")
    asyncio.run(run())
    s = router.stats()
    assert s["total"] == 2
    assert "fast_pct" in s
    assert "strong_pct" in s
