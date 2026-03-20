"""Tests for context_filter module."""
import pytest
from agent_swarm.context_filter import ContextFilter, ContextPolicy


class FakeTask:
    """Minimal task stub for testing."""
    def __init__(self, metadata=None):
        self.metadata = metadata


class TestContextPolicy:
    def test_default_values(self):
        p = ContextPolicy()
        assert p.max_wave_history == 2
        assert p.max_selective_items == 3
        assert p.max_context_chars == 4000
        assert p.role_filter is None
        assert p.include_own_history is True
        assert p.exclude_patterns == []

    def test_preset_minimal(self):
        p = ContextPolicy.MINIMAL
        assert p.max_wave_history == 1
        assert p.max_selective_items == 1
        assert p.max_context_chars == 2000

    def test_preset_standard(self):
        p = ContextPolicy.STANDARD
        assert p.max_wave_history == 2
        assert p.max_selective_items == 3
        assert p.max_context_chars == 4000

    def test_preset_full(self):
        p = ContextPolicy.FULL
        assert p.max_wave_history == 10
        assert p.max_selective_items == 10
        assert p.max_context_chars == 20000


class TestContextFilter:
    def test_no_policy_passthrough(self):
        task = FakeTask(metadata=None)
        ctx = {"wave_history": [1, 2, 3], "other": "data"}
        result = ContextFilter.filter(task, ctx)
        assert result is ctx  # same object, no filtering

    def test_wave_history_limit_list(self):
        task = FakeTask()
        ctx = {"wave_history": ["w1", "w2", "w3", "w4"]}
        policy = ContextPolicy(max_wave_history=2, max_context_chars=100000)
        result = ContextFilter.filter(task, ctx, policy=policy)
        assert result["wave_history"] == ["w3", "w4"]

    def test_wave_history_limit_dict(self):
        task = FakeTask()
        ctx = {"wave_history": {"a": 1, "b": 2, "c": 3}}
        policy = ContextPolicy(max_wave_history=2, max_context_chars=100000)
        result = ContextFilter.filter(task, ctx, policy=policy)
        assert result["wave_history"] == {"b": 2, "c": 3}

    def test_selective_items_limit(self):
        task = FakeTask()
        items = [{"role": "a"}, {"role": "b"}, {"role": "c"}, {"role": "d"}]
        ctx = {"selective_context": items}
        policy = ContextPolicy(max_selective_items=2, max_context_chars=100000)
        result = ContextFilter.filter(task, ctx, policy=policy)
        assert len(result["selective_context"]) == 2
        assert result["selective_context"] == items[:2]

    def test_role_filter(self):
        task = FakeTask()
        items = [{"role": "analyst"}, {"role": "coder"}, {"role": "analyst"}]
        ctx = {"selective_context": items}
        policy = ContextPolicy(
            role_filter=["analyst"], max_selective_items=10, max_context_chars=100000
        )
        result = ContextFilter.filter(task, ctx, policy=policy)
        assert all(i["role"] == "analyst" for i in result["selective_context"])
        assert len(result["selective_context"]) == 2

    def test_dep_context_passthrough(self):
        task = FakeTask()
        ctx = {"dep_context": "important deps", "wave_history": ["w1", "w2", "w3"]}
        policy = ContextPolicy(max_wave_history=1, max_context_chars=100000)
        result = ContextFilter.filter(task, ctx, policy=policy)
        assert result["dep_context"] == "important deps"

    def test_exclude_patterns(self):
        task = FakeTask()
        ctx = {"info": "secret_key=abc123 and more data"}
        policy = ContextPolicy(exclude_patterns=["secret_key=abc123"], max_context_chars=100000)
        result = ContextFilter.filter(task, ctx, policy=policy)
        assert "secret_key=abc123" not in result["info"]
        assert "[FILTERED]" in result["info"]

    def test_char_budget_truncation(self):
        task = FakeTask()
        ctx = {"text": "A" * 500}
        policy = ContextPolicy(max_context_chars=100)
        result = ContextFilter.filter(task, ctx, policy=policy)
        assert len(result["text"]) < 500
        assert result["text"].endswith("...[truncated]")

    def test_policy_from_task_metadata_dict(self):
        task = FakeTask(metadata={"context_policy": {"max_wave_history": 1, "max_context_chars": 100000}})
        ctx = {"wave_history": ["w1", "w2", "w3"]}
        result = ContextFilter.filter(task, ctx)
        assert result["wave_history"] == ["w3"]

    def test_policy_from_task_metadata_object(self):
        policy = ContextPolicy(max_wave_history=1, max_context_chars=100000)
        task = FakeTask(metadata={"context_policy": policy})
        ctx = {"wave_history": ["w1", "w2", "w3"]}
        result = ContextFilter.filter(task, ctx)
        assert result["wave_history"] == ["w3"]

    def test_other_keys_copied(self):
        task = FakeTask()
        ctx = {"wave_history": ["w1"], "custom_key": "value"}
        policy = ContextPolicy(max_wave_history=1, max_context_chars=100000)
        result = ContextFilter.filter(task, ctx, policy=policy)
        assert result["custom_key"] == "value"

    def test_no_mutation_of_input(self):
        task = FakeTask()
        original_waves = ["w1", "w2", "w3"]
        ctx = {"wave_history": original_waves[:]}
        policy = ContextPolicy(max_wave_history=1, max_context_chars=100000)
        ContextFilter.filter(task, ctx, policy=policy)
        assert ctx["wave_history"] == original_waves  # original unchanged
