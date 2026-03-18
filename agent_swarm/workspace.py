"""Isolated Workspace — ephemeral per-run execution sandbox.

Each run gets its own workspace. Contexts don't leak between runs.
After completion, only artifacts are collected; the workspace is cleaned up.

Usage:
    from agent_swarm.workspace import WorkspaceManager

    wm = WorkspaceManager("./workspaces")
    ws = wm.create("run_abc123")

    ws.write_file("plan.md", "# Plan\n...")
    ws.exec("pytest tests/ -q")
    artifacts = ws.collect_artifacts(["*.md", "*.json"])

    wm.cleanup("run_abc123")  # Remove workspace
"""

__all__ = ['Workspace', 'WorkspaceManager']
import glob
import json
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Workspace:
    """An isolated execution environment for a single run."""
    run_id: str
    path: str
    created_at: float = field(default_factory=time.time)
    files_written: List[str] = field(default_factory=list)
    commands_run: List[Dict] = field(default_factory=list)
    artifacts: List[Dict] = field(default_factory=list)

    def write_file(self, name: str, content: str) -> str:
        """Write a file into the workspace."""
        fpath = os.path.join(self.path, name)
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        with open(fpath, "w") as f:
            f.write(content)
        self.files_written.append(name)
        return fpath

    def read_file(self, name: str) -> Optional[str]:
        """Read a file from the workspace."""
        fpath = os.path.join(self.path, name)
        if not os.path.isfile(fpath):
            return None
        with open(fpath, "r", errors="replace") as f:
            return f.read()

    def list_files(self, pattern: str = "*") -> List[str]:
        """List files in workspace matching pattern."""
        return [os.path.relpath(f, self.path)
                for f in glob.glob(os.path.join(self.path, "**", pattern), recursive=True)
                if os.path.isfile(f)]

    def exec(self, command: str, timeout: int = 60) -> Dict:
        """Execute a shell command inside the workspace."""
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=self.path,
            )
            record = {
                "command": command, "returncode": result.returncode,
                "stdout": result.stdout[:5000], "stderr": result.stderr[:2000],
                "timestamp": time.time(),
            }
        except subprocess.TimeoutExpired:
            record = {"command": command, "returncode": -1,
                      "stdout": "", "stderr": f"Timeout after {timeout}s",
                      "timestamp": time.time()}
        except Exception as e:
            record = {"command": command, "returncode": -1,
                      "stdout": "", "stderr": str(e),
                      "timestamp": time.time()}
        self.commands_run.append(record)
        return record

    def collect_artifacts(self, patterns: List[str] = None) -> List[Dict]:
        """Collect output artifacts from workspace."""
        if patterns is None:
            patterns = ["*.md", "*.json", "*.txt", "*.html", "*.csv"]
        artifacts = []
        for pat in patterns:
            for fpath in glob.glob(os.path.join(self.path, "**", pat), recursive=True):
                if os.path.isfile(fpath):
                    rel = os.path.relpath(fpath, self.path)
                    size = os.path.getsize(fpath)
                    artifacts.append({
                        "name": rel, "size": size,
                        "path": fpath, "type": os.path.splitext(fpath)[1],
                    })
        self.artifacts = artifacts
        return artifacts

    def to_dict(self) -> Dict:
        return {
            "run_id": self.run_id, "path": self.path,
            "created_at": self.created_at,
            "files_written": self.files_written,
            "commands_run": len(self.commands_run),
            "artifacts": len(self.artifacts),
        }


class WorkspaceManager:
    """Manage isolated workspaces for runs."""

    def __init__(self, base_dir: str = None):
        self.base_dir = base_dir or os.path.expanduser("~/.agent-swarm/workspaces")
        os.makedirs(self.base_dir, exist_ok=True)
        self._workspaces: Dict[str, Workspace] = {}

    def create(self, run_id: str, copy_from: str = None) -> Workspace:
        """Create a new isolated workspace for a run."""
        ws_path = os.path.join(self.base_dir, run_id)
        os.makedirs(ws_path, exist_ok=True)

        if copy_from and os.path.isdir(copy_from):
            # Clone source directory into workspace (for code review, etc.)
            for item in os.listdir(copy_from):
                src = os.path.join(copy_from, item)
                dst = os.path.join(ws_path, item)
                if os.path.isdir(src):
                    if item not in (".git", "__pycache__", "node_modules", ".venv"):
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                elif os.path.isfile(src):
                    shutil.copy2(src, dst)

        ws = Workspace(run_id=run_id, path=ws_path)
        self._workspaces[run_id] = ws
        return ws

    def get(self, run_id: str) -> Optional[Workspace]:
        return self._workspaces.get(run_id)

    def cleanup(self, run_id: str, keep_artifacts: bool = True) -> List[Dict]:
        """Clean up workspace. Optionally preserve artifacts."""
        ws = self._workspaces.get(run_id)
        if not ws:
            return []

        artifacts = []
        if keep_artifacts:
            artifacts = ws.collect_artifacts()
            # Copy artifacts to a permanent location
            artifact_dir = os.path.join(self.base_dir, "_artifacts", run_id)
            os.makedirs(artifact_dir, exist_ok=True)
            for a in artifacts:
                try:
                    dst = os.path.join(artifact_dir, a["name"])
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(a["path"], dst)
                    a["archived_path"] = dst
                except Exception:
                    pass

        # Remove workspace
        try:
            shutil.rmtree(ws.path)
        except Exception:
            pass

        del self._workspaces[run_id]
        return artifacts

    def list_workspaces(self) -> List[Dict]:
        return [ws.to_dict() for ws in self._workspaces.values()]

    def cleanup_all(self, max_age_hours: float = 24):
        """Remove all workspaces older than max_age_hours."""
        cutoff = time.time() - max_age_hours * 3600
        to_remove = [rid for rid, ws in self._workspaces.items() if ws.created_at < cutoff]
        for rid in to_remove:
            self.cleanup(rid)
        return len(to_remove)
