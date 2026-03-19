"""Tests for attention.py — Softmax, RMSNorm, Block, Budget, Metrics."""
import math
import pytest
from agent_swarm.attention import (
    softmax, rmsnorm_score,
    softmax_weight_context, select_relevant_context_enhanced,
    compress_block, build_wave_context,
    adaptive_budget, AttentionMap, AttentionMapBuilder,
)


# ================================================================
#  Minimal TF-IDF stub for testing
# ================================================================

class _StubTfIdf:
    """Mimics skill_bank._tfidf interface for isolated tests."""
    def update(self, corpus):
        self._corpus = corpus

    def score(self, query, doc):
        q_words = set(query.lower().split())
        d_words = set(doc.lower().split())
        overlap = q_words & d_words
        if not q_words:
            return 0.0
        return len(overlap) / len(q_words)


class _StubResult:
    """Mimics TaskResult for select_relevant_context_enhanced tests."""
    def __init__(self, output, role="Worker", success=True, wave=0):
        self.output = output
        self.role = role
        self.success = success
        self.wave = wave


# ================================================================
#  Feature 3: RMSNorm
# ================================================================

def test_rmsnorm_short():
    score = rmsnorm_score(1.0, 4)
    assert score == pytest.approx(0.5, abs=1e-6)  # 1/sqrt(4)


def test_rmsnorm_long():
    score = rmsnorm_score(1.0, 100)
    assert score == pytest.approx(0.1, abs=1e-6)  # 1/sqrt(100)


def test_rmsnorm_zero():
    assert rmsnorm_score(1.0, 0) == 0.0
    assert rmsnorm_score(0.0, 10) == 0.0
    assert rmsnorm_score(1.0, -5) == 0.0


# ================================================================
#  Feature 1: Softmax
# ================================================================

def test_softmax_uniform():
    scores = {"a": 1.0, "b": 1.0, "c": 1.0}
    result = softmax(scores)
    assert len(result) == 3
    for v in result.values():
        assert v == pytest.approx(1 / 3, abs=1e-6)
    assert sum(result.values()) == pytest.approx(1.0, abs=1e-6)


def test_softmax_skewed():
    scores = {"a": 10.0, "b": 1.0, "c": 0.0}
    result = softmax(scores)
    assert result["a"] > result["b"] > result["c"]
    assert sum(result.values()) == pytest.approx(1.0, abs=1e-6)


def test_softmax_single_dep():
    scores = {"only": 5.0}
    result = softmax(scores)
    assert result["only"] == 1.0


def test_softmax_empty():
    assert softmax({}) == {}


def test_softmax_budget_allocation():
    tfidf = _StubTfIdf()
    dep_ctx = {
        "t1": "data science machine learning " * 20,
        "t2": "cooking recipe kitchen " * 20,
    }
    result, weights = softmax_weight_context(
        "data science analysis", dep_ctx, tfidf, total_budget=200
    )
    # t1 should get more budget than t2
    assert weights["t1"] > weights["t2"]
    assert len(result) == 2


def test_softmax_weight_single_dep():
    tfidf = _StubTfIdf()
    dep_ctx = {"t1": "only one"}
    result, weights = softmax_weight_context("test", dep_ctx, tfidf)
    assert result == dep_ctx
    assert weights["t1"] == 1.0


# ================================================================
#  Feature 5: Cross-Wave
# ================================================================

def test_cross_wave_includes_deps():
    tfidf = _StubTfIdf()
    results = {
        "t0": _StubResult("data science analysis results", wave=0),
        "t1": _StubResult("cooking recipe for pasta", wave=0),
    }
    ctx, weights = select_relevant_context_enhanced(
        "data science", {"t_dep"}, results, tfidf
    )
    # t0 should be selected (relevant), not t1
    if ctx:
        assert "data" in ctx.lower()
    assert isinstance(weights, dict)


def test_cross_wave_top_k_limit():
    tfidf = _StubTfIdf()
    results = {
        f"t{i}": _StubResult(f"data analysis result {i}", wave=i % 3)
        for i in range(10)
    }
    ctx, weights = select_relevant_context_enhanced(
        "data analysis", set(), results, tfidf, top_k=3
    )
    assert len(weights) <= 3


def test_cross_wave_wave_info():
    tfidf = _StubTfIdf()
    results = {
        "t0": _StubResult("machine learning data", wave=0),
        "t1": _StubResult("machine learning model", wave=2),
    }
    ctx, weights = select_relevant_context_enhanced(
        "machine learning", set(), results, tfidf
    )
    if ctx:
        assert "waves" in ctx.lower() or "Related Context" in ctx


def test_cross_wave_no_results():
    tfidf = _StubTfIdf()
    ctx, weights = select_relevant_context_enhanced(
        "test", set(), {}, tfidf
    )
    assert ctx == ""
    assert weights == {}


# ================================================================
#  Feature 2: Block Compression
# ================================================================

def test_compress_basic():
    summaries = [
        "Wave 0: 2 ok, 0 failed\n  [R] Found data",
        "Wave 1: 1 ok, 1 failed\n  [A] Analysis done",
        "Wave 2: 3 ok, 0 failed\n  [W] Report written",
    ]
    block = compress_block(summaries, 0, 3)
    assert "Block 0-2" in block
    assert "Wave 0" in block
    assert "Wave 2" in block


def test_compress_empty():
    assert compress_block([], 0, 3) == ""
    assert compress_block(["wave"], 5, 10) == ""


def test_build_context():
    summaries = ["Wave 0: 2 ok", "Wave 1: 1 ok", "Wave 2: 3 ok"]
    blocks = ["[Block 0-2] Wave 0: 2 ok; Wave 1: 1 ok; Wave 2: 3 ok"]
    ctx = build_wave_context(summaries, blocks, block_size=3, current_wave=3)
    assert "[Previous Waves]" in ctx
    assert "Block 0-2" in ctx


def test_build_context_reduces_size():
    summaries = [f"Wave {i}: details " * 10 for i in range(9)]
    blocks = [
        compress_block(summaries, 0, 3),
        compress_block(summaries, 3, 6),
    ]
    full = "\n".join(summaries)
    hierarchical = build_wave_context(summaries, blocks, block_size=3, current_wave=9)
    # Hierarchical context should be shorter than all summaries combined
    assert len(hierarchical) < len(full)


def test_build_context_empty():
    assert build_wave_context([], [], 3, 0) == ""


# ================================================================
#  Feature 6: Adaptive Budget
# ================================================================

def test_adaptive_early_generous():
    early = adaptive_budget(1000, 0, 10, depth_factor=0.5)
    late = adaptive_budget(1000, 9, 10, depth_factor=0.5)
    assert early > late
    assert early == 1000  # First wave gets full budget


def test_adaptive_late_selective():
    budget = adaptive_budget(1000, 9, 10, depth_factor=1.0)
    # Last wave with factor 1.0: scale = 1 - 1.0 * 1.0 = 0 → min 50
    assert budget == 50


def test_adaptive_single_wave():
    budget = adaptive_budget(1000, 0, 1, depth_factor=0.5)
    assert budget == 1000


def test_adaptive_no_budget():
    assert adaptive_budget(0, 5, 10) == 0


def test_adaptive_flat_factor():
    b1 = adaptive_budget(1000, 0, 10, depth_factor=0.0)
    b2 = adaptive_budget(1000, 9, 10, depth_factor=0.0)
    assert b1 == b2 == 1000


# ================================================================
#  Feature 4: AttentionMap Metrics
# ================================================================

def test_record_immutable():
    m1 = AttentionMap()
    m2 = m1.record("t0", "t1", 0.8, 0)
    assert len(m1.entries) == 0  # Original unchanged
    assert len(m2.entries) == 1
    m3 = m2.record("t1", "t2", 0.5, 1)
    assert len(m2.entries) == 1  # m2 unchanged
    assert len(m3.entries) == 2


def test_locality_score():
    m = AttentionMap()
    # All adjacent-wave connections
    m = m.record("t0", "t1", 0.8, 0)
    m = m.record("t1", "t2", 0.6, 1)
    score = m.locality_score()
    assert score == pytest.approx(1.0)  # All local


def test_skip_connections():
    m = AttentionMap()
    m = m.record("t0", "t1", 0.8, 0)  # wave 0→0 (local)
    m = m.record("t0", "t3", 0.3, 3)  # wave 0→3 (skip)
    skips = m.skip_connections()
    assert len(skips) >= 1
    assert any(s[0] == "t0" and s[1] == "t3" for s in skips)


def test_skip_connections_empty():
    assert AttentionMap().skip_connections() == []


def test_heatmap():
    m = AttentionMap()
    m = m.record("t0", "t1", 0.8, 0)
    m = m.record("t1", "t2", 0.3, 1)
    hmap = m.ascii_heatmap()
    assert "Heatmap" in hmap
    assert "t0" in hmap
    assert "t1" in hmap
    assert "#" in hmap
    assert "Total entries: 2" in hmap


def test_heatmap_empty():
    assert "Empty" in AttentionMap().ascii_heatmap()


def test_locality_empty():
    assert AttentionMap().locality_score() == 0.0


# ================================================================
#  AttentionMapBuilder
# ================================================================

def test_builder_freeze():
    b = AttentionMapBuilder()
    b.record("t0", "t1", 0.8, 0)
    b.record("t1", "t2", 0.5, 1)
    m = b.freeze()
    assert isinstance(m, AttentionMap)
    assert len(m.entries) == 2
    assert m.entries[0] == ("t0", "t1", 0.8, 0)


def test_builder_freeze_empty():
    m = AttentionMapBuilder().freeze()
    assert m.entries == ()
    assert m.locality_score() == 0.0


def test_builder_freeze_immutable():
    b = AttentionMapBuilder()
    b.record("a", "b", 0.5, 0)
    m1 = b.freeze()
    b.record("c", "d", 0.3, 1)
    m2 = b.freeze()
    assert len(m1.entries) == 1  # m1 unchanged
    assert len(m2.entries) == 2


# ================================================================
#  Edge Cases: Softmax
# ================================================================

def test_softmax_weight_all_zero_scores():
    tfidf = _StubTfIdf()
    dep_ctx = {
        "t1": "completely unrelated xyz",
        "t2": "also unrelated abc",
    }
    result, weights = softmax_weight_context("quantum physics", dep_ctx, tfidf)
    assert len(result) == 2
    assert isinstance(weights, dict)


def test_softmax_weight_no_rmsnorm():
    tfidf = _StubTfIdf()
    dep_ctx = {
        "t1": "data science machine learning",
        "t2": "cooking recipe kitchen",
    }
    result, weights = softmax_weight_context(
        "data science", dep_ctx, tfidf, use_rmsnorm=False
    )
    assert weights["t1"] > weights["t2"]


# ================================================================
#  Edge Cases: Cross-Wave
# ================================================================

def test_cross_wave_all_failed():
    tfidf = _StubTfIdf()
    results = {
        "t0": _StubResult("data analysis", success=False),
        "t1": _StubResult("more data", success=False),
    }
    ctx, weights = select_relevant_context_enhanced(
        "data", set(), results, tfidf
    )
    assert ctx == ""
    assert weights == {}


def test_cross_wave_excludes_deps():
    tfidf = _StubTfIdf()
    results = {
        "t0": _StubResult("data science analysis results", wave=0),
    }
    ctx, weights = select_relevant_context_enhanced(
        "data science", {"t0"}, results, tfidf
    )
    assert ctx == ""
    assert weights == {}


# ================================================================
#  Edge Cases: Block Compression
# ================================================================

def test_compress_block_end_before_start():
    assert compress_block(["wave 0"], 5, 2) == ""


def test_build_context_block_size_zero():
    summaries = ["Wave 0: ok", "Wave 1: ok"]
    ctx = build_wave_context(summaries, [], block_size=0, current_wave=2)
    assert "[Previous Waves]" in ctx


# ================================================================
#  Edge Cases: Adaptive Budget
# ================================================================

def test_adaptive_negative_factor_clamped():
    budget = adaptive_budget(1000, 5, 10, depth_factor=-0.5)
    assert budget == 1000  # Clamped to 0.0 → flat


def test_adaptive_factor_above_one_clamped():
    budget = adaptive_budget(1000, 9, 10, depth_factor=2.0)
    # Clamped to 1.0 → scale = 1 - 1.0 * 1.0 = 0 → min 50
    assert budget == 50
