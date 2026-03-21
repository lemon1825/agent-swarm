"""Tests for AutomationRule and AutomationRegistry (Cursor Automations)."""
import time
import pytest
from agent_swarm.tracker import (
    AutomationRule, AutomationRegistry, TriggerEvent, TrackerAdapter,
)


class TestAutomationRule:
    def test_frozen(self):
        rule = AutomationRule(name="test", trigger_source="*")
        with pytest.raises(AttributeError):
            rule.name = "other"

    def test_defaults(self):
        rule = AutomationRule(name="r1", trigger_source="github")
        assert rule.priority == 5
        assert rule.enabled is True
        assert rule.cooldown_s == 60.0
        assert rule.max_daily == 100


class TestAutomationRegistry:
    def _event(self, source="github", goal="Fix bug", ref="issue#1", context=""):
        return TriggerEvent(
            source=source, event_type="test", goal=goal, ref=ref, context=context,
        )

    def test_register_and_get(self):
        reg = AutomationRegistry()
        rule = AutomationRule(name="r1", trigger_source="*")
        reg.register(rule)
        assert reg.get("r1") is rule
        assert reg.count == 1

    def test_unregister(self):
        reg = AutomationRegistry()
        reg.register(AutomationRule(name="r1", trigger_source="*"))
        assert reg.unregister("r1") is True
        assert reg.get("r1") is None
        assert reg.unregister("nonexistent") is False

    def test_list_enabled(self):
        reg = AutomationRegistry()
        reg.register(AutomationRule(name="on", trigger_source="*", enabled=True))
        reg.register(AutomationRule(name="off", trigger_source="*", enabled=False))
        enabled = reg.list_enabled()
        assert len(enabled) == 1
        assert enabled[0].name == "on"

    def test_match_source_filter(self):
        reg = AutomationRegistry()
        reg.register(AutomationRule(name="gh", trigger_source="github", cooldown_s=0))
        reg.register(AutomationRule(name="all", trigger_source="*", cooldown_s=0))
        matched = reg.match(self._event(source="github"))
        assert len(matched) == 2
        matched_lin = reg.match(self._event(source="linear"))
        assert len(matched_lin) == 1
        assert matched_lin[0].name == "all"

    def test_match_pattern_filter(self):
        reg = AutomationRegistry()
        reg.register(AutomationRule(
            name="bug", trigger_source="*", trigger_pattern=r"bug|fix",
            cooldown_s=0,
        ))
        assert len(reg.match(self._event(goal="Fix bug"))) == 1
        assert len(reg.match(self._event(goal="Add feature"))) == 0

    def test_cooldown(self):
        reg = AutomationRegistry()
        reg.register(AutomationRule(name="r1", trigger_source="*", cooldown_s=60))
        event = self._event()
        # First match succeeds
        m1 = reg.match(event)
        assert len(m1) == 1
        # Execute to update state
        reg.execute(event)
        # Second match fails (cooldown)
        m2 = reg.match(event)
        assert len(m2) == 0

    def test_daily_limit(self):
        reg = AutomationRegistry()
        reg.register(AutomationRule(name="r1", trigger_source="*", cooldown_s=0, max_daily=2))
        event = self._event()
        reg.execute(event)
        reg.execute(event)
        # Third should be blocked
        assert len(reg.match(event)) == 0

    def test_disabled_rule_skipped(self):
        reg = AutomationRegistry()
        reg.register(AutomationRule(name="off", trigger_source="*", enabled=False))
        assert len(reg.match(self._event())) == 0

    def test_execute_returns_run_ids(self):
        reg = AutomationRegistry()  # no tracker
        reg.register(AutomationRule(name="r1", trigger_source="*", cooldown_s=0))
        ids = reg.execute(self._event())
        assert len(ids) == 1
        assert ids[0] is None  # no tracker = None run_id

    def test_execute_uses_action_template(self):
        reg = AutomationRegistry()
        reg.register(AutomationRule(
            name="r1", trigger_source="*",
            action="Auto: {goal}", cooldown_s=0,
        ))
        reg.execute(self._event(goal="test"))
        log = reg.execution_log()
        assert len(log) == 1
        assert log[0]["rule"] == "r1"

    def test_execution_log_limit(self):
        reg = AutomationRegistry()
        reg.register(AutomationRule(name="r1", trigger_source="*", cooldown_s=0, max_daily=200))
        for i in range(100):
            reg.execute(self._event(goal=f"goal-{i}"))
        assert len(reg.execution_log(limit=10)) == 10

    def test_thread_safety(self):
        """Verify lock exists and registry doesn't crash under basic use."""
        reg = AutomationRegistry()
        assert hasattr(reg, '_lock')
        reg.register(AutomationRule(name="r1", trigger_source="*", cooldown_s=0))
        reg.execute(self._event())
        assert reg.count == 1
