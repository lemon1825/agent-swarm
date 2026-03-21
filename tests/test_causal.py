"""Tests for causal attribution graph."""
import pytest
from agent_swarm.causal import (
    CausalEdge, CausalGraph, CausalAttribution,
    compute_influence, counterfactual_influence,
)


class TestCausalEdge:
    def test_frozen(self):
        e = CausalEdge("a", "b", 0.8, "dependency")
        with pytest.raises(AttributeError):
            e.cause_task = "c"

    def test_with_score(self):
        e = CausalEdge("a", "b", 0.8, "dependency")
        e2 = e.with_score(0.5)
        assert e2.influence_score == 0.5
        assert e.influence_score == 0.8  # original unchanged


class TestCausalGraph:
    def test_empty_graph(self):
        g = CausalGraph()
        assert len(g.edges) == 0
        assert len(g.task_ids) == 0

    def test_add_edge_immutable(self):
        g1 = CausalGraph()
        g2 = g1.add_edge("a", "b", 0.8, "dependency")
        assert len(g1.edges) == 0  # original unchanged
        assert len(g2.edges) == 1

    def test_add_edge_clamps_score(self):
        g = CausalGraph()
        g = g.add_edge("a", "b", 1.5, "dep")
        g = g.add_edge("c", "d", -0.5, "dep")
        assert g.edges[0].influence_score == 1.0
        assert g.edges[1].influence_score == 0.0

    def test_task_ids(self):
        g = CausalGraph()
        g = g.add_edge("a", "b", 0.8, "dep")
        g = g.add_edge("b", "c", 0.9, "dep")
        assert g.task_ids == {"a", "b", "c"}

    def test_get_causes(self):
        g = CausalGraph()
        g = g.add_edge("a", "c", 0.8, "dep")
        g = g.add_edge("b", "c", 0.7, "context")
        causes = g.get_causes("c")
        assert len(causes) == 2
        assert {e.cause_task for e in causes} == {"a", "b"}

    def test_get_effects(self):
        g = CausalGraph()
        g = g.add_edge("a", "b", 0.8, "dep")
        g = g.add_edge("a", "c", 0.7, "dep")
        effects = g.get_effects("a")
        assert len(effects) == 2

    def test_record_outcome(self):
        g = CausalGraph()
        g = g.add_edge("a", "b", 0.8, "dep")
        g = g.record_outcome("a", True)
        g = g.record_outcome("b", False)
        assert g._outcomes["a"] is True
        assert g._outcomes["b"] is False

    def test_find_root_tasks(self):
        g = CausalGraph()
        g = g.add_edge("a", "b", 0.8, "dep")
        g = g.add_edge("b", "c", 0.9, "dep")
        g = g.add_edge("a", "c", 0.5, "context")
        roots = g.find_root_tasks()
        assert roots == ["a"]

    def test_find_root_tasks_multiple(self):
        g = CausalGraph()
        g = g.add_edge("a", "c", 0.8, "dep")
        g = g.add_edge("b", "c", 0.7, "dep")
        roots = g.find_root_tasks()
        assert set(roots) == {"a", "b"}

    def test_trace_root_cause(self):
        g = CausalGraph()
        g = g.add_edge("a", "b", 0.8, "dep")
        g = g.add_edge("b", "c", 0.9, "dep")
        g = g.add_edge("c", "d", 0.7, "dep")
        chain = g.trace_root_cause("d")
        assert len(chain) == 3
        causes = [e.cause_task for e in chain]
        assert "a" in causes

    def test_trace_root_cause_max_depth(self):
        g = CausalGraph()
        for i in range(20):
            g = g.add_edge(f"t{i}", f"t{i+1}", 0.8, "dep")
        chain = g.trace_root_cause("t20", max_depth=5)
        # Linear chain: 5 BFS levels = exactly 5 edges
        assert len(chain) == 5

    def test_trace_root_cause_cycle_safe(self):
        g = CausalGraph()
        g = g.add_edge("a", "b", 0.8, "dep")
        g = g.add_edge("b", "a", 0.7, "retry")
        chain = g.trace_root_cause("b")
        # Should not infinite loop
        assert len(chain) >= 1


class TestCausalAttribution:
    def test_attribute_linear(self):
        g = CausalGraph()
        g = g.add_edge("a", "b", 0.8, "dep")
        g = g.add_edge("b", "c", 0.6, "dep")
        attr = g.attribute("c")
        assert attr.task_id == "c"
        assert attr.primary_cause is not None
        assert len(attr.contributing_tasks) == 2

    def test_attribute_no_causes(self):
        g = CausalGraph()
        attr = g.attribute("orphan")
        assert attr.total_influence == 0
        assert attr.contributing_tasks == ()
        assert attr.primary_cause is None

    def test_attribution_report(self):
        g = CausalGraph()
        g = g.add_edge("research", "analysis", 0.8, "dependency")
        g = g.add_edge("analysis", "report", 0.9, "dependency")
        g = g.record_outcome("research", True)
        g = g.record_outcome("analysis", True)
        g = g.record_outcome("report", False)
        report = g.attribution_report()
        assert "Causal Attribution Report" in report
        assert "research" in report
        assert "report" in report
        assert "dependency" in report

    def test_attribution_report_empty(self):
        g = CausalGraph()
        assert "[Empty CausalGraph]" == g.attribution_report()


class TestComputeInfluence:
    def test_none_cause(self):
        assert compute_influence(None, None) == 0.2

    def test_successful_cause_high_influence(self):
        class R:
            success = True
            output = "x" * 600
            duration_ms = 100.0
            tokens_used = 50
        score = compute_influence(R(), R())
        assert score > 0.7

    def test_failed_cause_low_influence(self):
        class R:
            success = False
            output = ""
            duration_ms = 10.0
            tokens_used = 0
        score = compute_influence(R(), R())
        assert score < 0.5

    def test_no_output_low_volume(self):
        class R:
            success = True
            output = ""
            duration_ms = 50.0
            tokens_used = 0
        score = compute_influence(R(), None)
        assert 0.0 <= score <= 1.0

    def test_score_bounded(self):
        class R:
            success = True
            output = "a" * 10000
            duration_ms = 999.0
            tokens_used = 500
        score = compute_influence(R(), R())
        assert 0.0 <= score <= 1.0


class TestCounterfactualInfluence:
    def test_no_effects(self):
        g = CausalGraph().add_edge("a", "b", 0.8, "dep")
        assert counterfactual_influence(g, "b", {}) == 0.0

    def test_critical_root(self):
        class R:
            success = True
        g = CausalGraph()
        g = g.add_edge("root", "b", 0.8, "dep")
        g = g.add_edge("root", "c", 0.8, "dep")
        g = g.add_edge("b", "d", 0.8, "dep")
        results = {"root": R(), "b": R(), "c": R(), "d": R()}
        score = counterfactual_influence(g, "root", results)
        assert score > 0.5  # root affects 3/3 downstream tasks

    def test_leaf_no_impact(self):
        g = CausalGraph()
        g = g.add_edge("a", "leaf", 0.8, "dep")
        score = counterfactual_influence(g, "leaf", {})
        assert score == 0.0


class TestFromDAGResults:
    def test_from_dag_results(self):
        class FakeTask:
            def __init__(self, id, deps):
                self.id = id
                self.dependencies = deps

        class FakeResult:
            def __init__(self, success):
                self.success = success

        tasks = [
            FakeTask("t1", []),
            FakeTask("t2", ["t1"]),
            FakeTask("t3", ["t1", "t2"]),
        ]
        results = {
            "t1": FakeResult(True),
            "t2": FakeResult(True),
            "t3": FakeResult(False),
        }
        graph = CausalGraph.from_dag_results(results, tasks)
        assert len(graph.edges) == 3
        assert graph._outcomes["t3"] is False
        roots = graph.find_root_tasks()
        assert "t1" in roots
