"""Run State Machine — Symphony-inspired implementation run lifecycle.

Transforms Agent Swarm from a "call-and-wait engine" into an "operational job system."
Each run is a first-class object with a lifecycle, proof bundle, and audit trail.

States:
    queued → planning → implementing → testing → awaiting_approval → completed
                ↓            ↓           ↓              ↓
              failed       failed      failed         rejected
                                                        ↓
                                                     retrying → implementing

Usage:
    from agent_swarm.run_machine import RunMachine, RunConfig

    machine = RunMachine()

    # Submit a run
    run_id = machine.submit(RunConfig(
        goal="Fix authentication bug",
        trigger="github_issue",
        trigger_ref="issue#42",
        tasks=[SubTask(...)],
    ))

    # Run executes through state machine automatically
    # Or step manually:
    await machine.execute(run_id, swarm)

    # Get proof bundle
    proof = machine.get_proof(run_id)
    print(proof.summary())
"""

__all__ = ['RunState', 'TRANSITIONS', 'StateTransition', 'ProofBundle', 'RunConfig', 'Run', 'RunMachine']
import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class RunState(str, Enum):
    QUEUED = "queued"
    PLANNING = "planning"
    IMPLEMENTING = "implementing"
    TESTING = "testing"
    AWAITING_APPROVAL = "awaiting_approval"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in (RunState.COMPLETED, RunState.FAILED, RunState.REJECTED, RunState.CANCELLED)


# Valid state transitions
TRANSITIONS = {
    RunState.QUEUED: [RunState.PLANNING, RunState.CANCELLED],
    RunState.PLANNING: [RunState.IMPLEMENTING, RunState.FAILED],
    RunState.IMPLEMENTING: [RunState.TESTING, RunState.FAILED],
    RunState.TESTING: [RunState.AWAITING_APPROVAL, RunState.COMPLETED, RunState.FAILED],
    RunState.AWAITING_APPROVAL: [RunState.COMPLETED, RunState.REJECTED, RunState.RETRYING],
    RunState.RETRYING: [RunState.IMPLEMENTING, RunState.FAILED],
    RunState.REJECTED: [RunState.RETRYING, RunState.CANCELLED],
    RunState.COMPLETED: [],
    RunState.FAILED: [RunState.RETRYING, RunState.CANCELLED],
    RunState.CANCELLED: [],
}


@dataclass
class StateTransition:
    """Record of a state change."""
    from_state: str
    to_state: str
    timestamp: float = field(default_factory=time.time)
    reason: str = ""
    actor: str = ""  # "system", "user", "supervisor", "approver"


@dataclass
class ProofBundle:
    """Structured evidence of a run's execution and results.

    This is what gets attached to PRs, issues, approval requests.
    """
    run_id: str = ""
    goal: str = ""
    trigger: str = ""           # github_issue, linear, manual, webhook, schedule
    trigger_ref: str = ""       # issue#42, LIN-123

    # What happened
    state: str = "queued"
    state_history: List[StateTransition] = field(default_factory=list)

    # What changed
    tasks_completed: List[Dict] = field(default_factory=list)    # [{id, role, output_preview, time_s, tokens}]
    tasks_failed: List[Dict] = field(default_factory=list)       # [{id, role, error}]
    files_changed: List[str] = field(default_factory=list)
    artifacts: List[Dict] = field(default_factory=list)          # [{name, type, path_or_content}]

    # Validation
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    validation_summary: str = ""
    ontology_violations: List[str] = field(default_factory=list)

    # Approval
    approval_status: str = ""   # pending, approved, rejected
    approved_by: str = ""
    approval_notes: str = ""

    # Cost
    total_tokens: int = 0
    total_cost_usd: float = 0
    execution_time_s: float = 0
    llm_calls: int = 0

    # Skills
    skills_evolved: List[str] = field(default_factory=list)
    skills_promoted: List[str] = field(default_factory=list)

    # Next
    next_steps: List[str] = field(default_factory=list)
    follow_up_runs: List[str] = field(default_factory=list)

    # Timestamps
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0

    def summary(self) -> str:
        lines = [
            f"═══ Proof Bundle: {self.run_id} ═══",
            f"Goal: {self.goal}",
            f"Trigger: {self.trigger} ({self.trigger_ref})" if self.trigger_ref else f"Trigger: {self.trigger}",
            f"State: {self.state}",
            f"",
            f"Tasks: {len(self.tasks_completed)} completed, {len(self.tasks_failed)} failed",
            f"Tests: {self.tests_passed}/{self.tests_run} passed",
            f"Tokens: {self.total_tokens:,} | Cost: ${self.total_cost_usd:.4f} | Time: {self.execution_time_s:.1f}s",
        ]
        if self.ontology_violations:
            lines.append(f"Ontology violations: {len(self.ontology_violations)}")
        if self.approval_status:
            lines.append(f"Approval: {self.approval_status} ({self.approved_by})")
        if self.skills_evolved:
            lines.append(f"Skills evolved: {', '.join(self.skills_evolved)}")
        if self.next_steps:
            lines.append(f"Next: {', '.join(self.next_steps[:3])}")
        if self.files_changed:
            lines.append(f"Files: {', '.join(self.files_changed[:5])}")

        lines.append(f"\nState history:")
        for t in self.state_history:
            lines.append(f"  {t.from_state} → {t.to_state} ({t.reason}) [{t.actor}]")

        return "\n".join(lines)

    def to_dict(self) -> Dict:
        d = {
            "run_id": self.run_id, "goal": self.goal,
            "trigger": self.trigger, "trigger_ref": self.trigger_ref,
            "state": self.state,
            "state_history": [{"from": t.from_state, "to": t.to_state,
                              "reason": t.reason, "actor": t.actor,
                              "timestamp": t.timestamp} for t in self.state_history],
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "files_changed": self.files_changed,
            "artifacts": self.artifacts,
            "tests": {"run": self.tests_run, "passed": self.tests_passed, "failed": self.tests_failed},
            "validation_summary": self.validation_summary,
            "ontology_violations": self.ontology_violations,
            "approval": {"status": self.approval_status, "by": self.approved_by, "notes": self.approval_notes},
            "cost": {"tokens": self.total_tokens, "usd": self.total_cost_usd,
                     "time_s": self.execution_time_s, "llm_calls": self.llm_calls},
            "skills": {"evolved": self.skills_evolved, "promoted": self.skills_promoted},
            "next_steps": self.next_steps,
            "created_at": self.created_at, "completed_at": self.completed_at,
        }
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False, default=str)

    @staticmethod
    def _coerce_tests(meta: Dict) -> Dict[str, int]:
        tests = meta.get("tests", {}) or {}
        return {
            "run": int(tests.get("run", meta.get("tests_run", 0)) or 0),
            "passed": int(tests.get("passed", meta.get("tests_passed", 0)) or 0),
            "failed": int(tests.get("failed", meta.get("tests_failed", 0)) or 0),
        }

    @staticmethod
    def _coerce_approval(meta: Dict) -> Dict[str, str]:
        approval = meta.get("approval", {}) or {}
        return {
            "status": str(approval.get("status", meta.get("approval_status", "")) or ""),
            "by": str(approval.get("by", meta.get("approved_by", "")) or ""),
            "notes": str(approval.get("notes", meta.get("approval_notes", "")) or ""),
        }

    @classmethod
    def from_result(cls, run_id: str, goal: str, result: Dict, trigger: str = "manual", trigger_ref: str = "") -> 'ProofBundle':
        """Create proof bundle from Swarm.run() result."""
        meta = result.get("metadata", {})
        results = result.get("results", {})
        tests = cls._coerce_tests(meta)
        approval = cls._coerce_approval(meta)

        completed = []
        failed = []
        for tid, tr in results.items():
            entry = {"id": tid, "role": tr.role, "time_s": round(tr.duration_ms / 1000, 2),
                     "tokens": getattr(tr, 'tokens_used', 0), "attempts": tr.attempts}
            if tr.success:
                entry["output_preview"] = (str(tr.output) or "")[:200]
                completed.append(entry)
            else:
                entry["error"] = tr.error or "; ".join(tr.validation_failures)
                failed.append(entry)

        validation_summary = meta.get("validation_summary", "")
        if not validation_summary and meta.get("errors"):
            validation_summary = "; ".join(f"{k}: {v}" for k, v in meta["errors"].items())[:500]

        return cls(
            run_id=run_id, goal=goal,
            trigger=trigger, trigger_ref=trigger_ref,
            tasks_completed=completed, tasks_failed=failed,
            files_changed=list(meta.get("files_changed", []) or []),
            artifacts=list(meta.get("artifacts", []) or []),
            tests_run=tests["run"], tests_passed=tests["passed"], tests_failed=tests["failed"],
            validation_summary=validation_summary,
            ontology_violations=[str(w) for w in meta.get("plan_quality", {}).get("ontology_warnings", [])],
            approval_status=approval["status"], approved_by=approval["by"], approval_notes=approval["notes"],
            total_tokens=meta.get("total_tokens", 0),
            total_cost_usd=meta.get("budget_spent_usd", 0),
            execution_time_s=meta.get("execution_time_s", 0),
            llm_calls=meta.get("llm_calls_used", 0),
            skills_evolved=list(meta.get("skills_evolved", []) or []),
            skills_promoted=list(meta.get("skills_promoted", []) or []),
            next_steps=list(meta.get("next_steps", []) or []),
            follow_up_runs=list(meta.get("follow_up_runs", []) or []),
        )


@dataclass
class RunConfig:
    """Configuration for submitting a run."""
    goal: str
    tasks: List = field(default_factory=list)
    trigger: str = "manual"         # manual, github_issue, webhook, schedule, linear
    trigger_ref: str = ""           # issue#42, webhook_id
    playbook: str = ""
    pack: str = ""
    context: str = ""
    requires_approval: bool = False
    max_retries: int = 2
    priority: int = 5               # 1=highest, 10=lowest
    workspace_id: str = ""          # For isolated workspace
    metadata: Dict = field(default_factory=dict)


@dataclass
class Run:
    """A managed implementation run with full lifecycle."""
    id: str = field(default_factory=lambda: f"run_{uuid.uuid4().hex[:8]}")
    config: RunConfig = field(default_factory=lambda: RunConfig(goal=""))
    state: RunState = RunState.QUEUED
    proof: ProofBundle = field(default_factory=ProofBundle)
    retry_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def transition(self, new_state: RunState, reason: str = "", actor: str = "system") -> bool:
        """Attempt state transition. Returns True if valid."""
        if new_state not in TRANSITIONS.get(self.state, []):
            return False
        self.proof.state_history.append(StateTransition(
            from_state=self.state.value, to_state=new_state.value,
            reason=reason, actor=actor,
        ))
        self.state = new_state
        self.proof.state = new_state.value
        self.updated_at = time.time()
        return True


class RunMachine:
    """Manages run lifecycle — submit, execute, track, retry.

    This is the core of the "operational job system" model.
    """

    def __init__(self, persist_dir: str = None):
        self._runs: Dict[str, Run] = {}
        self._queue: List[str] = []  # Run IDs in priority order
        self._persist_dir = persist_dir
        self._on_state_change: List[Callable] = []
        if persist_dir:
            os.makedirs(persist_dir, exist_ok=True)
            self._load()

    def on_state_change(self, callback: Callable):
        """Register callback: callback(run_id, old_state, new_state, reason)"""
        self._on_state_change.append(callback)

    def submit(self, config: RunConfig) -> str:
        """Submit a new run. Returns run_id."""
        run = Run(config=config)
        run.proof.run_id = run.id
        run.proof.goal = config.goal
        run.proof.trigger = config.trigger
        run.proof.trigger_ref = config.trigger_ref
        self._runs[run.id] = run
        self._queue.append(run.id)
        self._queue.sort(key=lambda rid: self._runs[rid].config.priority)
        self._persist_run(run)
        return run.id

    def get(self, run_id: str) -> Optional[Run]:
        return self._runs.get(run_id)

    def get_proof(self, run_id: str) -> Optional[ProofBundle]:
        run = self._runs.get(run_id)
        return run.proof if run else None

    def list_runs(self, state: RunState = None) -> List[Dict]:
        runs = self._runs.values()
        if state:
            runs = [r for r in runs if r.state == state]
        return [{"id": r.id, "goal": r.config.goal[:60], "state": r.state.value,
                 "trigger": r.config.trigger, "priority": r.config.priority,
                 "created": r.created_at} for r in sorted(runs, key=lambda r: r.created_at, reverse=True)]

    def queue_size(self) -> int:
        return len([r for r in self._queue if self._runs[r].state == RunState.QUEUED])

    async def execute(self, run_id: str, swarm, approval_callback: Callable = None):
        """Execute a run through the full state machine."""
        run = self._runs.get(run_id)
        if not run:
            raise ValueError(f"Run not found: {run_id}")

        try:
            # PLANNING
            self._transition(run, RunState.PLANNING, "Starting execution")

            # IMPLEMENTING
            self._transition(run, RunState.IMPLEMENTING, "Plan ready, executing tasks")

            result = await swarm.run(
                run.config.goal,
                tasks=run.config.tasks if run.config.tasks else None,
                context=run.config.context,
                playbook=run.config.playbook or None,
            )

            # Build proof from result
            proof = ProofBundle.from_result(run.id, run.config.goal, result,
                                           run.config.trigger, run.config.trigger_ref)
            # Merge into existing proof (keep state history)
            history = run.proof.state_history
            run.proof = proof
            run.proof.state_history = history
            run.proof.state = run.state.value

            # TESTING
            self._transition(run, RunState.TESTING, f"{proof.tests_passed}/{proof.tests_run} tests")

            has_failures = len(proof.tasks_failed) > 0

            # APPROVAL
            if run.config.requires_approval or has_failures:
                self._transition(run, RunState.AWAITING_APPROVAL,
                                 "Approval required" if run.config.requires_approval else "Has failures, needs review")
                run.proof.approval_status = "pending"

                if approval_callback:
                    approved = await approval_callback(run.id, run.proof.summary())
                    if approved:
                        run.proof.approval_status = "approved"
                        run.proof.approved_by = "callback"
                        self._transition(run, RunState.COMPLETED, "Approved")
                    else:
                        run.proof.approval_status = "rejected"
                        self._transition(run, RunState.REJECTED, "Rejected by approver")
                        if run.retry_count < run.config.max_retries:
                            run.retry_count += 1
                            self._transition(run, RunState.RETRYING, f"Retry {run.retry_count}/{run.config.max_retries}")
                            return await self.execute(run_id, swarm, approval_callback)
                # If no callback, stay in AWAITING_APPROVAL
            elif not has_failures:
                self._transition(run, RunState.COMPLETED, f"{len(proof.tasks_completed)} tasks succeeded")
            else:
                # Failures but no approval required — retry or fail
                if run.retry_count < run.config.max_retries:
                    run.retry_count += 1
                    self._transition(run, RunState.RETRYING, f"Retry {run.retry_count}/{run.config.max_retries}")
                    return await self.execute(run_id, swarm, approval_callback)
                self._transition(run, RunState.FAILED, f"{len(proof.tasks_failed)} tasks failed, retries exhausted")

            run.proof.completed_at = time.time()
            self._persist_run(run)
            return run.proof

        except Exception as e:
            self._transition(run, RunState.FAILED, f"Exception: {str(e)[:100]}")
            run.proof.completed_at = time.time()
            self._persist_run(run)
            raise

    def approve(self, run_id: str, approved: bool, by: str = "user", notes: str = "") -> bool:
        """Manually approve/reject a run in AWAITING_APPROVAL state."""
        run = self._runs.get(run_id)
        if not run or run.state != RunState.AWAITING_APPROVAL:
            return False
        run.proof.approved_by = by
        run.proof.approval_notes = notes
        if approved:
            run.proof.approval_status = "approved"
            self._transition(run, RunState.COMPLETED, f"Approved by {by}")
        else:
            run.proof.approval_status = "rejected"
            self._transition(run, RunState.REJECTED, f"Rejected by {by}: {notes}")
        self._persist_run(run)
        return True

    def cancel(self, run_id: str, reason: str = "User cancelled") -> bool:
        run = self._runs.get(run_id)
        if not run or run.state.is_terminal:
            return False
        self._transition(run, RunState.CANCELLED, reason)
        self._persist_run(run)
        return True

    def _transition(self, run: Run, new_state: RunState, reason: str, actor: str = "system"):
        old = run.state
        if run.transition(new_state, reason, actor):
            for cb in self._on_state_change:
                try:
                    cb(run.id, old.value, new_state.value, reason)
                except Exception:
                    pass

    def _persist_run(self, run: Run):
        if not self._persist_dir:
            return
        path = os.path.join(self._persist_dir, f"{run.id}.json")
        with open(path, "w") as f:
            json.dump({
                "id": run.id, "state": run.state.value,
                "config": {"goal": run.config.goal, "trigger": run.config.trigger,
                           "trigger_ref": run.config.trigger_ref, "priority": run.config.priority},
                "proof": run.proof.to_dict(),
                "retry_count": run.retry_count,
                "created_at": run.created_at,
            }, f, indent=2, default=str)

    def _load(self):
        if not self._persist_dir:
            return
        for fname in os.listdir(self._persist_dir):
            if not fname.endswith(".json"):
                continue
            try:
                with open(os.path.join(self._persist_dir, fname)) as f:
                    data = json.load(f)
                config = RunConfig(goal=data["config"]["goal"],
                                   trigger=data["config"].get("trigger", "manual"),
                                   trigger_ref=data["config"].get("trigger_ref", ""))
                run = Run(id=data["id"], config=config,
                          state=RunState(data["state"]),
                          created_at=data.get("created_at", 0))
                self._runs[run.id] = run
            except Exception:
                pass
