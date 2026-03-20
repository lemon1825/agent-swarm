"""Tests for Safety Guards module."""
import pytest
from agent_swarm.safety import CarefulGuard, FreezeGuard, GuardChain, GuardAction, GuardResult


class TestGuardAction:
    def test_enum_values(self):
        assert GuardAction.ALLOW.value == "allow"
        assert GuardAction.WARN.value == "warn"
        assert GuardAction.BLOCK.value == "block"


class TestCarefulGuard:
    def test_detects_rm_rf(self):
        guard = CarefulGuard()
        result = guard.check("rm -rf /tmp/data")
        assert result.action == GuardAction.WARN
        assert "Recursive force delete" in result.reason
        assert result.guard_name == "CarefulGuard"

    def test_detects_drop_table(self):
        guard = CarefulGuard()
        result = guard.check("DROP TABLE users")
        assert result.action == GuardAction.WARN
        assert "SQL table drop" in result.reason

    def test_detects_git_force_push(self):
        guard = CarefulGuard()
        result = guard.check("git push origin main --force")
        assert result.action == GuardAction.WARN
        assert "Git force push" in result.reason

    def test_detects_git_force_push_short(self):
        guard = CarefulGuard()
        result = guard.check("git push -f origin main")
        assert result.action == GuardAction.WARN

    def test_allows_safe_commands(self):
        guard = CarefulGuard()
        result = guard.check("ls -la /home/user")
        assert result.action == GuardAction.ALLOW

    def test_allows_safe_git(self):
        guard = CarefulGuard()
        result = guard.check("git push origin main")
        assert result.action == GuardAction.ALLOW

    def test_allows_delete_with_where(self):
        guard = CarefulGuard()
        result = guard.check("DELETE FROM users WHERE id = 5")
        assert result.action == GuardAction.ALLOW

    def test_custom_action_block(self):
        guard = CarefulGuard(action=GuardAction.BLOCK)
        result = guard.check("rm -rf /")
        assert result.action == GuardAction.BLOCK

    def test_custom_patterns(self):
        guard = CarefulGuard(extra_patterns=[(r'\bdangerous_cmd\b', "Custom danger")])
        result = guard.check("run dangerous_cmd now")
        assert result.action == GuardAction.WARN
        assert "Custom danger" in result.reason

    def test_case_insensitive(self):
        guard = CarefulGuard()
        result = guard.check("drop table users")
        assert result.action == GuardAction.WARN


class TestFreezeGuard:
    def test_blocks_frozen_path(self):
        guard = FreezeGuard(frozen_paths=["/etc/config"])
        result = guard.check("modify /etc/config/app.yaml")
        assert result.action == GuardAction.BLOCK
        assert "frozen" in result.reason

    def test_allows_non_frozen_path(self):
        guard = FreezeGuard(frozen_paths=["/etc/config"])
        result = guard.check("modify /tmp/scratch.txt")
        assert result.action == GuardAction.ALLOW

    def test_freeze_unfreeze(self):
        guard = FreezeGuard()
        guard.freeze("/data/prod")
        assert "/data/prod" in guard.frozen_paths
        result = guard.check("edit /data/prod/db.conf")
        assert result.action == GuardAction.BLOCK

        guard.unfreeze("/data/prod")
        assert "/data/prod" not in guard.frozen_paths
        result = guard.check("edit /data/prod/db.conf")
        assert result.action == GuardAction.ALLOW

    def test_empty_frozen_allows_all(self):
        guard = FreezeGuard()
        result = guard.check("anything goes")
        assert result.action == GuardAction.ALLOW


class TestGuardChain:
    def test_returns_most_restrictive(self):
        careful = CarefulGuard(action=GuardAction.WARN)
        freeze = FreezeGuard(frozen_paths=["/prod"])
        chain = GuardChain([careful, freeze])

        result = chain.check("rm -rf /prod/data")
        assert result.action == GuardAction.BLOCK  # FreezeGuard is more restrictive

    def test_check_all_returns_all_results(self):
        careful = CarefulGuard()
        freeze = FreezeGuard(frozen_paths=["/prod"])
        chain = GuardChain([careful, freeze])

        results = chain.check_all("rm -rf /prod/data")
        assert len(results) == 2
        actions = {r.action for r in results}
        assert GuardAction.WARN in actions
        assert GuardAction.BLOCK in actions

    def test_all_allow(self):
        careful = CarefulGuard()
        freeze = FreezeGuard()
        chain = GuardChain([careful, freeze])

        result = chain.check("echo hello")
        assert result.action == GuardAction.ALLOW

    def test_add_returns_new_chain(self):
        chain = GuardChain()
        new_chain = chain.add(CarefulGuard())
        assert len(new_chain._guards) == 1
        assert len(chain._guards) == 0  # Original unchanged (immutable pattern)

    def test_empty_chain_allows(self):
        chain = GuardChain()
        result = chain.check("anything")
        assert result.action == GuardAction.ALLOW
