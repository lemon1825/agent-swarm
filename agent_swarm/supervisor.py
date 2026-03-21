"""Supervisor Runtime — OTP-inspired failure isolation and worker management.

Ensures one failing run doesn't take down the whole system.
Manages concurrency, retry policies, and graceful degradation.

Usage:
    from agent_swarm.supervisor import Supervisor

    sup = Supervisor(
        max_concurrent=3,
        max_retries_per_run=2,
        restart_delay_s=5.0,
    )

    sup.start(swarm, run_machine)
    # Supervisor continuously processes queued runs
    # Failed runs are retried or escalated
    # Concurrent runs are limited
"""

__all__ = ['SupervisorConfig', 'WorkerSlot', 'Supervisor']
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .run_machine import RunMachine, RunState, Run

logger = logging.getLogger("agent_swarm.supervisor")


@dataclass
class SupervisorConfig:
    """Supervisor configuration."""
    max_concurrent: int = 3           # Max simultaneous runs
    max_retries_per_run: int = 2      # Max retries before giving up
    restart_delay_s: float = 5.0      # Delay between retries
    poll_interval_s: float = 2.0      # Queue check interval
    max_run_time_s: float = 600.0     # Max time for a single run
    max_queue_size: int = 100         # Max queued runs
    pause_on_consecutive_failures: int = 5  # Pause after N consecutive failures
    health_check_interval_s: float = 30.0
    isolation: str = "none"           # "none" or "worktree" (Cursor-style git isolation)


@dataclass
class WorkerSlot:
    """Tracks an active worker (running run)."""
    run_id: str
    task: asyncio.Task = None
    started_at: float = field(default_factory=time.time)


class Supervisor:
    """OTP-inspired supervisor for Agent Swarm runs.

    - Processes queued runs with concurrency control
    - Isolates failures (one bad run can't crash others)
    - Retries with backoff
    - Pauses after consecutive failures
    - Health monitoring
    """

    def __init__(self, config: SupervisorConfig = None):
        self.config = config or SupervisorConfig()
        self._workers: Dict[str, WorkerSlot] = {}
        self._consecutive_failures = 0
        self._paused = False
        self._running = False
        self._stats = {
            "total_started": 0, "total_completed": 0, "total_failed": 0,
            "total_retried": 0, "uptime_start": 0,
        }
        self._on_run_complete: List[Callable] = []
        self._on_run_failed: List[Callable] = []
        self._on_pause: List[Callable] = []
        self._worktree_mgr = None
        if self.config.isolation == "worktree":
            try:
                from .worktree import WorktreeManager
                self._worktree_mgr = WorktreeManager()
            except ImportError:
                logger.warning("Worktree isolation requested but worktree module unavailable")

    def on_complete(self, cb: Callable):
        """callback(run_id, proof)"""
        self._on_run_complete.append(cb)

    def on_failed(self, cb: Callable):
        """callback(run_id, error)"""
        self._on_run_failed.append(cb)

    def on_pause(self, cb: Callable):
        """callback(reason)"""
        self._on_pause.append(cb)

    async def start(self, swarm, run_machine: RunMachine,
                    approval_callback: Callable = None):
        """Start the supervisor loop. Runs until stopped."""
        self._running = True
        self._stats["uptime_start"] = time.time()
        logger.info("Supervisor started (max_concurrent=%d)", self.config.max_concurrent)

        while self._running:
            try:
                await self._tick(swarm, run_machine, approval_callback)
            except Exception as e:
                logger.error("Supervisor tick error: %s", e)
            await asyncio.sleep(self.config.poll_interval_s)

    def stop(self):
        """Stop the supervisor."""
        self._running = False
        logger.info("Supervisor stopping")

    def pause(self, reason: str = "Manual pause"):
        """Pause processing (existing runs continue)."""
        self._paused = True
        for cb in self._on_pause:
            try: cb(reason)
            except Exception: pass
        logger.warning("Supervisor paused: %s", reason)

    def resume(self):
        """Resume processing."""
        self._paused = False
        self._consecutive_failures = 0
        logger.info("Supervisor resumed")

    @property
    def active_workers(self) -> int:
        return len(self._workers)

    def stats(self) -> Dict:
        uptime = time.time() - self._stats["uptime_start"] if self._stats["uptime_start"] else 0
        return {
            **self._stats,
            "active_workers": self.active_workers,
            "max_concurrent": self.config.max_concurrent,
            "paused": self._paused,
            "consecutive_failures": self._consecutive_failures,
            "uptime_s": round(uptime),
        }

    async def _tick(self, swarm, run_machine: RunMachine, approval_callback):
        """One supervisor tick: clean dead workers, start new ones."""
        # Clean completed/failed workers
        done_workers = []
        for rid, worker in self._workers.items():
            if worker.task and worker.task.done():
                done_workers.append(rid)
                try:
                    worker.task.result()  # Propagate exceptions for logging
                except Exception as e:
                    logger.warning("Worker %s failed: %s", rid, e)

            # Timeout check
            if time.time() - worker.started_at > self.config.max_run_time_s:
                if worker.task and not worker.task.done():
                    worker.task.cancel()
                    logger.warning("Worker %s timed out after %.0fs", rid, self.config.max_run_time_s)
                done_workers.append(rid)

        for rid in set(done_workers):
            self._workers.pop(rid, None)

        # Don't start new runs if paused
        if self._paused:
            return

        # Check consecutive failure pause
        if self._consecutive_failures >= self.config.pause_on_consecutive_failures:
            self.pause(f"{self._consecutive_failures} consecutive failures")
            return

        # Start new runs from queue (up to concurrency limit)
        available_slots = self.config.max_concurrent - self.active_workers
        if available_slots <= 0:
            return

        queued = run_machine.list_runs(RunState.QUEUED)
        for run_info in queued[:available_slots]:
            rid = run_info["id"]
            if rid in self._workers:
                continue

            # Start worker
            task = asyncio.create_task(
                self._run_worker(rid, swarm, run_machine, approval_callback)
            )
            self._workers[rid] = WorkerSlot(run_id=rid, task=task)
            self._stats["total_started"] += 1
            logger.info("Started worker for %s (%d/%d slots)",
                        rid, self.active_workers, self.config.max_concurrent)

    async def _run_worker(self, run_id: str, swarm, run_machine, approval_callback):
        """Execute a single run with failure isolation."""
        try:
            proof = await run_machine.execute(run_id, swarm, approval_callback)

            run = run_machine.get(run_id)
            if run and run.state == RunState.COMPLETED:
                self._stats["total_completed"] += 1
                self._consecutive_failures = 0
                for cb in self._on_run_complete:
                    try: cb(run_id, proof)
                    except Exception: pass
            elif run and run.state == RunState.FAILED:
                self._stats["total_failed"] += 1
                self._consecutive_failures += 1
                for cb in self._on_run_failed:
                    try: cb(run_id, str(proof) if proof else "Unknown error")
                    except Exception: pass

        except asyncio.CancelledError:
            logger.info("Worker %s cancelled", run_id)
        except Exception as e:
            self._stats["total_failed"] += 1
            self._consecutive_failures += 1
            logger.error("Worker %s crashed: %s", run_id, e)
            for cb in self._on_run_failed:
                try: cb(run_id, str(e))
                except Exception: pass

    async def execute_one(self, run_id: str, swarm, run_machine, approval_callback=None):
        """Execute a single run immediately (bypass queue). For testing/manual use."""
        return await self._run_worker(run_id, swarm, run_machine, approval_callback)
