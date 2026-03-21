"""Tests for worktree isolation (Cursor-inspired parallel agent isolation)."""
import os
import time
import pytest
from unittest.mock import patch, MagicMock
from agent_swarm.worktree import (
    WorktreeConfig, WorktreeInfo, WorktreeManager, WorktreeError,
)


class TestWorktreeConfig:
    def test_defaults(self):
        cfg = WorktreeConfig()
        assert cfg.base_dir == ".agent-swarm/worktrees"
        assert cfg.branch_prefix == "agent/"
        assert cfg.auto_cleanup is True
        assert cfg.git_executable == "git"

    def test_frozen(self):
        cfg = WorktreeConfig()
        with pytest.raises(AttributeError):
            cfg.base_dir = "other"


class TestWorktreeInfo:
    def test_frozen(self):
        info = WorktreeInfo(
            run_id="run-1", path="/tmp/wt", branch="agent/run-1",
            created_at=time.time(),
        )
        with pytest.raises(AttributeError):
            info.run_id = "other"

    def test_exists_false(self):
        info = WorktreeInfo(
            run_id="run-1", path="/nonexistent/path", branch="agent/run-1",
            created_at=time.time(),
        )
        assert info.exists is False

    def test_age(self):
        info = WorktreeInfo(
            run_id="run-1", path="/tmp", branch="agent/run-1",
            created_at=time.time() - 60,
        )
        assert info.age_seconds >= 59


class TestWorktreeManager:
    def test_init_defaults(self):
        mgr = WorktreeManager()
        assert mgr.config.base_dir == ".agent-swarm/worktrees"
        assert mgr.list_active() == []

    def test_repo_root(self):
        mgr = WorktreeManager(repo_root="/my/repo")
        assert mgr.repo_root == "/my/repo"

    def test_base_dir_relative(self):
        mgr = WorktreeManager(repo_root="/my/repo")
        expected = os.path.join("/my/repo", ".agent-swarm/worktrees")
        assert mgr.base_dir == expected

    def test_base_dir_absolute(self):
        cfg = WorktreeConfig(base_dir="/absolute/path")
        mgr = WorktreeManager(config=cfg)
        assert mgr.base_dir == "/absolute/path"

    def test_get_nonexistent(self):
        mgr = WorktreeManager()
        assert mgr.get("nonexistent") is None

    @patch.object(WorktreeManager, '_run_git')
    @patch.object(WorktreeManager, '_is_git_repo', return_value=True)
    @patch('os.makedirs')
    def test_create_worktree(self, mock_makedirs, mock_is_git, mock_git):
        mock_git.return_value = ""
        mgr = WorktreeManager(repo_root="/repo")
        info = mgr.create("run-42")

        assert info.run_id == "run-42"
        assert "run-42" in info.branch
        assert "run-42" in info.path
        assert info in mgr.list_active()
        mock_git.assert_called()

    @patch.object(WorktreeManager, '_run_git')
    @patch.object(WorktreeManager, '_is_git_repo', return_value=True)
    @patch('os.makedirs')
    def test_create_idempotent(self, mock_makedirs, mock_is_git, mock_git):
        mock_git.return_value = ""
        mgr = WorktreeManager(repo_root="/repo")
        info1 = mgr.create("run-42")
        info2 = mgr.create("run-42")
        assert info1 is info2  # same object returned
        assert len(mgr.list_active()) == 1

    @patch.object(WorktreeManager, '_is_git_repo', return_value=False)
    def test_create_not_git_repo(self, mock_is_git):
        mgr = WorktreeManager()
        with pytest.raises(WorktreeError, match="Not a git repository"):
            mgr.create("run-42")

    @patch.object(WorktreeManager, '_run_git')
    @patch.object(WorktreeManager, '_is_git_repo', return_value=True)
    @patch('os.makedirs')
    def test_cleanup(self, mock_makedirs, mock_is_git, mock_git):
        mock_git.return_value = ""
        mgr = WorktreeManager(repo_root="/repo")
        mgr.create("run-42")
        assert len(mgr.list_active()) == 1

        result = mgr.cleanup("run-42")
        assert result is True
        assert len(mgr.list_active()) == 0

    def test_cleanup_nonexistent(self):
        mgr = WorktreeManager()
        assert mgr.cleanup("nonexistent") is False

    @patch.object(WorktreeManager, '_run_git')
    @patch.object(WorktreeManager, '_is_git_repo', return_value=True)
    @patch('os.makedirs')
    def test_cleanup_all(self, mock_makedirs, mock_is_git, mock_git):
        mock_git.return_value = ""
        mgr = WorktreeManager(repo_root="/repo")
        mgr.create("run-1")
        mgr.create("run-2")
        mgr.create("run-3")
        assert len(mgr.list_active()) == 3

        count = mgr.cleanup_all()
        assert count == 3
        assert len(mgr.list_active()) == 0

    @patch.object(WorktreeManager, '_run_git')
    @patch.object(WorktreeManager, '_is_git_repo', return_value=True)
    @patch('os.makedirs')
    def test_cleanup_stale(self, mock_makedirs, mock_is_git, mock_git):
        mock_git.return_value = ""
        mgr = WorktreeManager(repo_root="/repo")

        # Create worktrees with different ages
        info1 = mgr.create("old-run")
        info2 = mgr.create("new-run")

        # Manually adjust created_at for old-run
        mgr._active["old-run"] = WorktreeInfo(
            run_id="old-run", path=info1.path, branch=info1.branch,
            created_at=time.time() - 7200,  # 2 hours old
        )

        count = mgr.cleanup_stale(max_age_seconds=3600)
        assert count == 1
        assert mgr.get("old-run") is None
        assert mgr.get("new-run") is not None

    @patch.object(WorktreeManager, '_run_git')
    @patch.object(WorktreeManager, '_is_git_repo', return_value=True)
    @patch('os.makedirs')
    def test_sanitize_run_id(self, mock_makedirs, mock_is_git, mock_git):
        mock_git.return_value = ""
        mgr = WorktreeManager(repo_root="/repo")
        info = mgr.create("run/with spaces\\backslash")
        assert "/" not in info.path.split("worktrees")[-1].lstrip("/\\")
        assert "\\" not in info.branch.split("agent/")[-1]


    @patch.object(WorktreeManager, '_run_git')
    @patch.object(WorktreeManager, '_is_git_repo', return_value=True)
    @patch('os.makedirs')
    def test_sanitize_path_traversal(self, mock_makedirs, mock_is_git, mock_git):
        """'..' in run_id must be sanitized to prevent path traversal."""
        mock_git.return_value = ""
        mgr = WorktreeManager(repo_root="/repo")
        info = mgr.create("../../etc/passwd")
        assert ".." not in info.path
        assert ".." not in info.branch

    @patch.object(WorktreeManager, '_run_git')
    @patch.object(WorktreeManager, '_is_git_repo', return_value=True)
    @patch('os.makedirs')
    def test_sanitize_empty_id(self, mock_makedirs, mock_is_git, mock_git):
        """Empty run_id must produce a safe fallback name."""
        mock_git.return_value = ""
        mgr = WorktreeManager(repo_root="/repo")
        info = mgr.create("")
        assert len(info.branch) > len("agent/")
        assert "unnamed" in info.path or "run-" in info.path

    @patch.object(WorktreeManager, '_run_git')
    @patch.object(WorktreeManager, '_is_git_repo', return_value=True)
    @patch('os.makedirs')
    def test_sanitize_dash_start_id(self, mock_makedirs, mock_is_git, mock_git):
        """Run IDs starting with dash must be prefixed to avoid git flag confusion."""
        mock_git.return_value = ""
        mgr = WorktreeManager(repo_root="/repo")
        info = mgr.create("-dangerous")
        safe_part = info.branch.split("agent/")[-1]
        assert not safe_part.startswith("-")

    @patch.object(WorktreeManager, '_run_git')
    @patch.object(WorktreeManager, '_is_git_repo', return_value=True)
    @patch('os.makedirs')
    def test_auto_cleanup_disabled_blocks_cleanup(self, mock_makedirs, mock_is_git, mock_git):
        """When auto_cleanup=False, cleanup() returns False unless force=True."""
        mock_git.return_value = ""
        cfg = WorktreeConfig(auto_cleanup=False)
        mgr = WorktreeManager(config=cfg, repo_root="/repo")
        mgr.create("run-1")
        assert mgr.cleanup("run-1") is False  # blocked
        assert mgr.get("run-1") is not None    # still active
        assert mgr.cleanup("run-1", force=True) is True  # force overrides
        assert mgr.get("run-1") is None


class TestSupervisorIsolation:
    def test_isolation_config(self):
        from agent_swarm.supervisor import SupervisorConfig
        cfg = SupervisorConfig(isolation="worktree")
        assert cfg.isolation == "worktree"

    def test_default_isolation_none(self):
        from agent_swarm.supervisor import SupervisorConfig
        cfg = SupervisorConfig()
        assert cfg.isolation == "none"
