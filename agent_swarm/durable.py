"""Durable Execution — persistent checkpoints that survive process restarts.

Zero dependencies. File-based JSON checkpoints.

When a swarm run is interrupted (crash, timeout, Ctrl+C), it can resume
from exactly where it left off.

Usage:
    from agent_swarm.durable import DurableCheckpoint

    # Create durable checkpoint store
    durable = DurableCheckpoint("./checkpoints")

    # Run with durable execution
    result = await swarm.run("goal", tasks=[...], checkpoint=durable.load("run_1"))

    # If interrupted, resume:
    result = await swarm.run("goal", tasks=[...], checkpoint=durable.load("run_1"))
    # → Completed tasks are skipped, execution resumes from last checkpoint

    # List all checkpoints
    durable.list()  # → [{"run_id": "run_1", "completed": 3, "total": 5, ...}]
"""

__all__ = ['DurableCheckpoint']
import json
import os
import time
from typing import Dict, List, Optional


class DurableCheckpoint:
    """File-based persistent checkpoint store."""

    def __init__(self, path: str = None):
        self.path = path or os.path.expanduser("~/.agent-swarm/checkpoints")
        os.makedirs(self.path, exist_ok=True)

    def _file(self, run_id: str) -> str:
        # Sanitize run_id for filesystem
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(run_id))
        return os.path.join(self.path, f"{safe}.json")

    def save(self, run_id: str, checkpoint: Dict):
        """Save checkpoint to disk. Called automatically by Swarm after each wave."""
        checkpoint["_durable_run_id"] = run_id
        checkpoint["_durable_saved_at"] = time.time()

        f = self._file(run_id)
        tmp = f + ".tmp"
        try:
            with open(tmp, "w") as fh:
                json.dump(checkpoint, fh, indent=2, ensure_ascii=False, default=str)
            os.replace(tmp, f)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def load(self, run_id: str) -> Optional[Dict]:
        """Load checkpoint from disk. Returns None if no checkpoint exists."""
        f = self._file(run_id)
        if not os.path.isfile(f):
            return None
        try:
            with open(f) as fh:
                return json.load(fh)
        except Exception:
            return None

    def delete(self, run_id: str) -> bool:
        """Delete a checkpoint."""
        f = self._file(run_id)
        if os.path.isfile(f):
            os.unlink(f)
            return True
        return False

    def list(self) -> List[Dict]:
        """List all saved checkpoints with summary info."""
        results = []
        for fname in os.listdir(self.path):
            if not fname.endswith(".json"):
                continue
            try:
                with open(os.path.join(self.path, fname)) as fh:
                    data = json.load(fh)
                completed = data.get("completed", {})
                results.append({
                    "run_id": data.get("_durable_run_id", fname[:-5]),
                    "completed_tasks": len(completed),
                    "saved_at": data.get("_durable_saved_at", 0),
                    "llm_calls": data.get("llm_calls", 0),
                    "file": fname,
                })
            except Exception:
                pass
        results.sort(key=lambda r: r["saved_at"], reverse=True)
        return results

    def cleanup(self, max_age_hours: float = 72):
        """Remove checkpoints older than max_age_hours."""
        cutoff = time.time() - max_age_hours * 3600
        removed = 0
        for fname in os.listdir(self.path):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(self.path, fname)
            try:
                with open(fpath) as fh:
                    data = json.load(fh)
                if data.get("_durable_saved_at", 0) < cutoff:
                    os.unlink(fpath)
                    removed += 1
            except Exception:
                pass
        return removed

    def create_hook(self, run_id: str):
        """Create a checkpoint callback for use with Swarm's event system.

        Usage:
            durable = DurableCheckpoint()
            swarm = Swarm(llm=my_llm, event_callback=durable.create_hook("run_1"))
        """
        store = self

        def hook(event, data):
            if hasattr(event, 'value'):
                event = event.value
            if event == "checkpoint_saved" and "checkpoint" in data:
                store.save(run_id, data["checkpoint"])
            elif event == "run_completed" and "checkpoint" in data:
                store.save(run_id, data["checkpoint"])
                # Also save final metadata
                store.save(f"{run_id}_final", data)
        return hook
