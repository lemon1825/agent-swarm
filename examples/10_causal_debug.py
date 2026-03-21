"""Causal Attribution — trace root causes of agent failures.

Demonstrates causal inference in agent DAG execution:
- Build causal graph from execution results
- Trace root cause of failures
- Counterfactual analysis: "what if this agent hadn't run?"
"""
from agent_swarm import CausalGraph, compute_influence, counterfactual_influence


class FakeResult:
    def __init__(self, success, output="", duration_ms=100, tokens_used=50):
        self.success = success
        self.output = output
        self.duration_ms = duration_ms
        self.tokens_used = tokens_used


def main():
    # Simulate a DAG execution where the report task failed
    graph = CausalGraph()
    graph = graph.add_edge("research", "analysis", 0.85, "dependency")
    graph = graph.add_edge("research", "fact_check", 0.7, "dependency")
    graph = graph.add_edge("analysis", "report", 0.9, "dependency")
    graph = graph.add_edge("fact_check", "report", 0.6, "dependency")

    # Record outcomes
    graph = graph.record_outcome("research", True)
    graph = graph.record_outcome("analysis", True)
    graph = graph.record_outcome("fact_check", False)  # failed!
    graph = graph.record_outcome("report", False)       # failed because of fact_check

    # Attribution report
    print(graph.attribution_report())
    print()

    # Root cause trace
    chain = graph.trace_root_cause("report")
    print("Root cause chain for 'report':")
    for edge in chain:
        print(f"  {edge.cause_task} → {edge.effect_task} "
              f"(influence={edge.influence_score:.2f}, mechanism={edge.mechanism})")

    # Counterfactual: what if research hadn't run?
    results = {
        "research": FakeResult(True, "findings " * 100, 500, 200),
        "analysis": FakeResult(True, "insights " * 50, 300, 100),
        "fact_check": FakeResult(False, "", 50, 10),
        "report": FakeResult(False, "", 100, 50),
    }
    cf = counterfactual_influence(graph, "research", results)
    print(f"\nCounterfactual: removing 'research' would impact {cf:.0%} of the pipeline")

    # Measured influence
    influence = compute_influence(results["research"], results["analysis"])
    print(f"Measured influence (research → analysis): {influence:.2f}")


if __name__ == "__main__":
    main()
