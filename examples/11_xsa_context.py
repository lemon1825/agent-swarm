"""XSA Context Exclusion — compare before/after self-context removal.

Demonstrates Exclusive Self Attention (Zhai, 2026):
- Core: sentence-level cosine filtering (stdlib)
- Pro: vector-space orthogonal projection (numpy)
"""
from agent_swarm.context_filter import orthogonal_project, ContextPolicy, ContextFilter


def demo_core_xsa():
    """Core stdlib XSA: sentence-level filtering."""
    print("=== Core XSA (stdlib) ===")

    self_output = (
        "The machine learning model uses gradient descent for optimization. "
        "Training requires large datasets and GPU resources."
    )

    context = (
        "The machine learning model uses gradient descent for optimization. "
        "Natural language processing has advanced with transformers. "
        "Training requires large datasets and GPU resources for efficiency. "
        "Reinforcement learning enables agents to learn from environment interaction."
    )

    filtered, similarity = orthogonal_project(context, self_output, strength=1.0)

    print(f"Original context ({len(context)} chars):")
    print(f"  {context[:100]}...")
    print(f"Filtered context ({len(filtered)} chars):")
    print(f"  {filtered[:100]}...")
    print(f"Self-similarity removed: {similarity:.0%}")
    print()


def demo_pro_xsa():
    """Pro numpy XSA: vector-space projection."""
    print("=== Pro XSA (numpy) ===")
    try:
        from agent_swarm.pro.xsa import VectorProjector, XSAConfig

        proj = VectorProjector(XSAConfig(strength=1.0, min_similarity=0.2))

        self_text = "Machine learning optimization with gradient descent on large datasets"
        texts = [
            "Machine learning optimization uses gradient descent algorithms on training data",
            "Web development frameworks like React and Django simplify frontend and backend",
            "Reinforcement learning agents explore environments to maximize reward signals",
        ]

        result = proj.project(texts, self_text)

        print(f"Input texts: {len(texts)}")
        print(f"Filtered texts: {len(result.filtered_texts)}")
        print(f"Removed: {result.removed_count}")
        print(f"Avg similarity: {result.avg_similarity:.2f}")
        print(f"Method: {result.projection_method}")
        for i, (text, sim) in enumerate(zip(texts, result.similarity_scores)):
            status = "REMOVED" if text not in result.filtered_texts else "KEPT"
            print(f"  [{status}] sim={sim:.2f} | {text[:60]}...")

    except ImportError:
        print("  (numpy not installed — Pro XSA unavailable)")
    print()


if __name__ == "__main__":
    demo_core_xsa()
    demo_pro_xsa()
