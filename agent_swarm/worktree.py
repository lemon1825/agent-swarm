"""Worktree Isolation — Git worktree management for parallel agent execution.

Inspired by Cursor's Background/Cloud Agents (2025-2026):
- Each parallel agent gets its own git worktree
- Isolated file modifications prevent agent conflicts
- Automatic cleanup after completion

Like separate workbenches in a workshop: each craftsman (agent) has their
own bench with their own copy of the materials. They can saw and hammer
without interfering with each other's work.

Usage:
    from agent_swarm.worktree import WorktreeManager, WorktreeConfig

    mgr = WorktreeManager(WorktreeConfig(base_dir=".agent-swarm/worktrees"))

    # Create isolated worktree for a run
    info = mgr.create("run-42")
    print(info.path, info.branch)

    # List active worktrees
    for wt in mgr.list_active():
        print(wt.run_id, wt.path)

    # Cleanup after completion
    mgr.cleanup("run-42")
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


__all__ = [
    "WorktreeConfig",
    "WorktreeInfo",
    "WorktreeManager",
    "WorktreeError",
]


class WorktreeError(Exception):
    """Error during worktree operations."""


@dataclass(frozen=True)
class WorktreeConfig:
    """Configuration for worktree isolation."""
    base_dir: str = ".agent-swarm/worktrees"
    branch_prefix: str = "agent/"
    auto_cleanup: bool = True
    git_executable: str = "git"


@dataclass(frozen=True)
class WorktreeInfo:
    """Information about a created worktree."""
    run_id: str
    path: str
    branch: str
    created_at: float
    base_ref: str = "HEAD"

    @property
    def exists(self) -> bool:
        return os.path.isdir(self.path)

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at


class WorktreeManager:
    """Git worktree manager for parallel agent execution.

    Provides isolated working directories for concurrent runs,
    preventing file conflicts between parallel agents.
    """

    def __init__(self, config: Optional[WorktreeConfig] = None, repo_root: Optional[str] = None):
        """
        Args:
            config: Worktree configuration
            repo_root: Root of the git repository. If None, uses cwd.
        """
        self.config = config or WorktreeConfig()
        self._repo_root = repo_root or os.getcwd()
        self._active: Dict[str, WorktreeInfo] = {}

    @property
    def repo_root(self) -> str:
        return self._repo_root

    @property
    def base_dir(self) -> str:
        base = self.config.base_dir
        if not os.path.isabs(base):
            return os.path.join(self._repo_root, base)
        return base

    def _run_git(self, *args: str, check: bool = True) -> str:
        """Run a git command and return stdout."""
        cmd = [self.config.git_executable] + list(args)
        try:
            result = subprocess.run(
                cmd,
                cwd=self._repo_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if check and result.returncode != 0:
                raise WorktreeError(
                    f"git {' '.join(args)} failed: {result.stderr.strip()}"
                )
            return result.stdout.strip()
        except FileNotFoundError:
            raise WorktreeError(f"git executable not found: {self.config.git_executable}")
        except subprocess.TimeoutExpired:
            raise WorktreeError(f"git command timed out: {' '.join(args)}")

    def _is_git_repo(self) -> bool:
        """Check if repo_root is a git repository."""
        try:
            self._run_git("rev-parse", "--is-inside-work-tree")
            return True
        except WorktreeError:
            return False

    def create(self, run_id: str, base_ref: str = "HEAD") -> WorktreeInfo:
        """Create a new worktree for a run.

        Args:
            run_id: Unique identifier for the run
            base_ref: Git ref to base the worktree on (default: HEAD)

        Returns:
            WorktreeInfo with path and branch details

        Raises:
            WorktreeError: If git operations fail
        """
        if run_id in self._active:
            return self._active[run_id]

        if not self._is_git_repo():
            raise WorktreeError(f"Not a git repository: {self._repo_root}")

        # Sanitize run_id for branch/path names
        safe_id = run_id.replace("/", "-").replace("\\", "-").replace(" ", "-").replace("..", "_")
        if not safe_id or safe_id.startswith("-"):
            safe_id = f"run-{safe_id.lstrip('-') or 'unnamed'}"
        branch = f"{self.config.branch_prefix}{safe_id}"
        wt_path = os.path.join(self.base_dir, safe_id)

        # Ensure base directory exists
        os.makedirs(self.base_dir, exist_ok=True)

        # Create worktree with new branch
        self._run_git("worktree", "add", "-b", branch, wt_path, base_ref)

        info = WorktreeInfo(
            run_id=run_id,
            path=wt_path,
            branch=branch,
            created_at=time.time(),
            base_ref=base_ref,
        )
        self._active[run_id] = info
        return info

    def cleanup(self, run_id: str, force: bool = False) -> bool:
        """Remove a worktree and its branch.

        Args:
            run_id: The run ID to clean up
            force: Force removal even with uncommitted changes

        Returns:
            True if cleanup succeeded, False if worktree not found
        """
        info = self._active.get(run_id)
        if info is None:
            return False

        # If auto_cleanup is disabled, skip unless force is True
        if not self.config.auto_cleanup and not force:
            return False

        # Remove worktree
        args = ["worktree", "remove"]
        if force:
            args.append("--force")
        args.append(info.path)

        try:
            self._run_git(*args)
        except WorktreeError:
            if force and os.path.isdir(info.path):
                shutil.rmtree(info.path, ignore_errors=True)
                self._run_git("worktree", "prune")

        # Delete the branch
        try:
            delete_flag = "-D" if force else "-d"
            self._run_git("branch", delete_flag, info.branch)
        except WorktreeError:
            pass  # Branch may already be deleted

        del self._active[run_id]
        return True

    def get(self, run_id: str) -> Optional[WorktreeInfo]:
        """Get info about an active worktree."""
        return self._active.get(run_id)

    def list_active(self) -> List[WorktreeInfo]:
        """List all active worktrees managed by this instance."""
        return list(self._active.values())

    def cleanup_all(self, force: bool = False) -> int:
        """Remove all managed worktrees. Returns count of cleaned up trees."""
        run_ids = list(self._active.keys())
        count = 0
        for run_id in run_ids:
            if self.cleanup(run_id, force=force):
                count += 1
        return count

    def cleanup_stale(self, max_age_seconds: float = 3600) -> int:
        """Remove worktrees older than max_age_seconds."""
        now = time.time()
        stale = [
            info.run_id for info in self._active.values()
            if now - info.created_at > max_age_seconds
        ]
        count = 0
        for run_id in stale:
            if self.cleanup(run_id, force=True):
                count += 1
        return count
