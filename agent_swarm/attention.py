"""Attention Residuals — softmax weighting, RMSNorm, block compression, budget.

All functions are pure and use only stdlib (math). Zero external dependencies.
Based on MoonshotAI's Attention Residuals paper: replace fixed residual
connections with softmax-weighted context propagation in DAG execution.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ================================================================
#  Feature 3: RMSNorm — normalize scores by output length
# ================================================================

def rmsnorm_score(raw_score: float, output_length: int) -> float:
    """Normalize a relevance score by sqrt(output_length).

    Prevents long outputs from dominating attention weights purely
    due to more TF-IDF term matches. Analogous to the 1/sqrt(d_k)
    scaling in transformer attention.
    """
    if output_length <= 0:
        return 0.0
    return raw_score / math.sqrt(output_length)


# ================================================================
#  Feature 1: Softmax — stable probability distribution over scores
# ================================================================

def softmax(scores: Dict[str, float], temperature: float = 1.0) -> Dict[str, float]:
    """Compute softmax over a dict of scores with temperature scaling.

    Uses max-subtraction for numerical stability: exp(x - max(x)).
    Temperature > 1 flattens distribution, < 1 sharpens it.
    """
    if not scores:
        return {}
    if len(scores) == 1:
        return {k: 1.0 for k in scores}
    t = max(temperature, 1e-8)
    scaled = {k: v / t for k, v in scores.items()}
    mx = max(scaled.values())
    exps = {k: math.exp(v - mx) for k, v in scaled.items()}
    total = sum(exps.values())
    if total == 0:
        uniform = 1.0 / len(scores)
        return {k: uniform for k in scores}
    return {k: v / total for k, v in exps.items()}


def softmax_weight_context(
    task_desc: str,
    dep_ctx: Dict[str, str],
    tfidf,
    total_budget: int = 0,
    use_rmsnorm: bool = True,
) -> Tuple[Dict[str, str], Dict[str, float]]:
    """Weight dependency context using softmax attention (Feature 1).

    Returns:
        (weighted_ctx, weights): The budget-allocated context dict
        and the raw softmax weight dict.
    """
    if not dep_ctx or len(dep_ctx) <= 1:
        weights = {k: 1.0 for k in dep_ctx} if dep_ctx else {}
        return dict(dep_ctx), weights

    corpus = [str(v)[:200] for v in dep_ctx.values()]
    tfidf.update(corpus)

    raw_scores = {}
    for (tid, output), doc in zip(dep_ctx.items(), corpus):
        score = tfidf.score(task_desc, doc)
        if use_rmsnorm:
            score = rmsnorm_score(score, len(output))
        raw_scores[tid] = score

    weights = softmax(raw_scores)

    if total_budget > 0:
        weighted = {}
        for tid, output in dep_ctx.items():
            alloc = max(50, int(total_budget * weights[tid]))
            weighted[tid] = output[:alloc] + "..." if len(output) > alloc else output
        return weighted, weights

    ranked = sorted(weights.items(), key=lambda x: -x[1])
    half = max(1, len(ranked) // 2)
    top_ids = {tid for tid, _ in ranked[:half]}
    weighted = {}
    for tid, output in dep_ctx.items():
        if tid in top_ids:
            weighted[tid] = output
        else:
            weighted[tid] = output[:100] + "..." if len(output) > 100 else output
    return weighted, weights


# ================================================================
#  Feature 5: Cross-Wave selective context (enhanced)
# ================================================================

def select_relevant_context_enhanced(
    task_desc: str,
    deps: set,
    results: Dict[str, object],
    tfidf,
    top_k: int = 5,
    threshold: float = 0.05,
    use_rmsnorm: bool = True,
) -> Tuple[str, Dict[str, float]]:
    """Cross-wave selective context with softmax weights (Feature 5).

    Picks top-k most relevant non-dependency results, applies RMSNorm
    and softmax weighting to produce ranked context.

    Returns:
        (context_str, weights): Formatted context and weight map.
    """
    if not results:
        return "", {}
    candidates = {
        tid: r for tid, r in results.items()
        if r.success and tid not in deps and r.output
    }
    if not candidates:
        return "", {}

    corpus = [r.output[:200] for r in candidates.values()]
    tfidf.update(corpus)

    raw_scores = {}
    for (tid, r), doc in zip(candidates.items(), corpus):
        score = tfidf.score(task_desc, doc)
        if use_rmsnorm:
            score = rmsnorm_score(score, len(r.output))
        raw_scores[tid] = score

    above = {tid: s for tid, s in raw_scores.items() if s > threshold}
    if not above:
        return "", {}

    weights = softmax(above)
    ranked = sorted(weights.items(), key=lambda x: -x[1])[:top_k]

    lines = []
    for tid, w in ranked:
        r = candidates[tid]
        lines.append(f"  [{r.role}|w={w:.2f}] {r.output[:150]}")

    wave_ids = set()
    for tid, _ in ranked:
        r = candidates[tid]
        if hasattr(r, "wave"):
            wave_ids.add(r.wave)
    wave_info = f" (from waves {sorted(wave_ids)})" if wave_ids else ""

    ctx = f"[Related Context{wave_info}]\n" + "\n".join(lines)
    return ctx, {tid: w for tid, w in ranked}


# ================================================================
#  Feature 2: Block compression — hierarchical wave summaries
# ================================================================

def compress_block(wave_summaries: List[str], block_start: int, block_end: int) -> str:
    """Compress a block of wave summaries into a single block summary.

    Extracts key information from each wave summary within the block
    range [block_start, block_end) and merges them.
    """
    if block_start >= len(wave_summaries):
        return ""
    end = min(block_end, len(wave_summaries))
    block_lines = wave_summaries[block_start:end]
    if not block_lines:
        return ""
    combined = "; ".join(line.split("\n")[0] for line in block_lines if line)
    return f"[Block {block_start}-{end - 1}] {combined}"


def build_wave_context(
    wave_summaries: List[str],
    block_summaries: List[str],
    block_size: int,
    current_wave: int,
) -> str:
    """Build hierarchical wave context for a task (Feature 2).

    Uses block summaries for older waves and detailed summaries
    for recent waves within the current block.
    """
    if not wave_summaries:
        return ""

    parts = []
    if block_summaries:
        parts.extend(block_summaries)

    current_block_start = (current_wave // block_size) * block_size if block_size > 0 else 0
    recent = wave_summaries[current_block_start:current_wave]
    if recent:
        parts.extend(recent)

    if not parts:
        return ""
    return "[Previous Waves]\n" + "\n".join(parts)


# ================================================================
#  Feature 6: Adaptive budget — depth-aware token allocation
# ================================================================

def adaptive_budget(
    total_budget: int,
    current_wave: int,
    total_waves: int,
    depth_factor: float = 0.5,
) -> int:
    """Compute adaptive context budget for a wave (Feature 6).

    Early waves get more budget (exploration), later waves get less
    (should be more focused). depth_factor controls the curve:
    0.0 = flat budget, 1.0 = aggressive reduction.
    """
    if total_budget <= 0:
        return 0
    if total_waves <= 1:
        return total_budget

    df = max(0.0, min(1.0, depth_factor))
    progress = current_wave / max(1, total_waves - 1)
    scale = 1.0 - df * progress
    return max(50, int(total_budget * scale))


# ================================================================
#  Feature 4: AttentionMap — metrics and visualization
# ================================================================

class AttentionMapBuilder:
    """Mutable builder for collecting attention entries during execution.

    Use this during DAG execution to avoid O(n^2) tuple concatenation,
    then call freeze() to produce an immutable AttentionMap.
    """
    def __init__(self):
        self._entries: List[Tuple[str, str, float, int]] = []

    def record(self, source: str, target: str, weight: float, wave: int) -> None:
        """Append an attention weight entry. Mutates in place (O(1) amortized)."""
        self._entries.append((source, target, weight, wave))

    def freeze(self) -> "AttentionMap":
        """Produce an immutable AttentionMap from collected entries."""
        return AttentionMap(entries=tuple(self._entries))


@dataclass(frozen=True)
class AttentionMap:
    """Immutable attention weight tracker for DAG execution.

    Each record() returns a new AttentionMap with the additional entry.
    Provides locality scoring, skip connection detection, and ASCII heatmap.

    For bulk collection during execution, prefer AttentionMapBuilder
    which avoids O(n^2) tuple concatenation.
    """
    entries: Tuple[Tuple[str, str, float, int], ...] = ()

    def record(self, source: str, target: str, weight: float, wave: int) -> "AttentionMap":
        """Record an attention weight. Returns new AttentionMap (immutable).

        Note: For hot loops, prefer AttentionMapBuilder to avoid O(n^2) copying.
        """
        return AttentionMap(
            entries=self.entries + ((source, target, weight, wave),)
        )

    def locality_score(self) -> float:
        """Fraction of attention that flows between adjacent waves.

        Higher scores indicate more local (sequential) information flow.
        Lower scores suggest more long-range skip connections.
        """
        if not self.entries:
            return 0.0
        wave_map = {}
        for src, tgt, w, wave in self.entries:
            wave_map[src] = wave_map.get(src, wave)
            wave_map[tgt] = wave_map.get(tgt, wave)
        local = 0
        total = 0
        for src, tgt, w, wave in self.entries:
            total += 1
            src_wave = wave_map.get(src, wave)
            tgt_wave = wave_map.get(tgt, wave)
            if abs(src_wave - tgt_wave) <= 1:
                local += 1
        return local / total if total > 0 else 0.0

    def skip_connections(self) -> List[Tuple[str, str, float, int]]:
        """Return entries where attention spans more than 1 wave gap."""
        if not self.entries:
            return []
        wave_map = {}
        for src, tgt, w, wave in self.entries:
            wave_map[src] = wave_map.get(src, wave)
            wave_map[tgt] = wave_map.get(tgt, wave)
        skips = []
        for src, tgt, w, wave in self.entries:
            src_wave = wave_map.get(src, wave)
            tgt_wave = wave_map.get(tgt, wave)
            if abs(src_wave - tgt_wave) > 1:
                skips.append((src, tgt, w, wave))
        return skips

    def ascii_heatmap(self, max_width: int = 40) -> str:
        """Render an ASCII heatmap of attention weights.

        Shows source→target pairs with bar-chart visualization.
        """
        if not self.entries:
            return "[Empty AttentionMap]"
        lines = ["Attention Heatmap:", "=" * max_width]
        max_w = max(w for _, _, w, _ in self.entries) if self.entries else 1.0
        max_w = max(max_w, 1e-8)
        for src, tgt, w, wave in self.entries:
            bar_len = int((w / max_w) * (max_width - 20))
            bar_len = max(1, bar_len)
            label = f"{src[:6]:>6}→{tgt[:6]:<6}"
            bar = "#" * bar_len
            lines.append(f"  {label} |{bar}| {w:.3f}")
        lines.append(f"Total entries: {len(self.entries)}")
        return "\n".join(lines)
