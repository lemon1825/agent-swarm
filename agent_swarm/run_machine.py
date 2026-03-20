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

__all__ = ['RunState', 'TRANSITIONS', 'StateTransition', 'ProofBundle', 'RunConfig', 'Run', 'RunMachine', 'ReviewGate', 'ReviewResult', 'SpecGate']
import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from .review import ReviewPipeline as _ReviewPipeline
except Exception:  # pragma: no cover
    _ReviewPipeline = None

logger = logging.getLogger("agent_swarm")


class RunState(str, Enum):
    QUEUED = "queued"
    PLANNING = "planning"
    SPEC_REVIEW = "spec_review"
    IMPLEMENTING = "implementing"
    TESTING = "testing"
    AWAITING_APPROVAL = "awaiting_approval"
    RETRYING = "retrying"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in (RunState.COMPLETED, RunState.FAILED, RunState.REJECTED, RunState.CANCELLED)


@dataclass
class ReviewResult:
    """Result from a review gate evaluation."""
    passed: bool
    issues: List[str] = field(default_factory=list)
    severity: str = "info"  # "critical", "important", "minor", "info"


@dataclass
class ReviewGate:
    """A review gate in the review pipeline.

    After TESTING passes, each gate runs in order. Required gates that fail
    block progression to COMPLETED.
    """
    name: str                          # "spec_compliance", "code_quality"
    reviewer: Callable                 # async (run_id, proof) -> ReviewResult
    required: bool = True              # must pass to proceed
    order: int = 0                     # execution order


@dataclass
class SpecGate:
    """Gate that validates spec/plan before implementation begins."""
    validator: Callable  # async (run_id: str, plan: Any) -> (bool, str)
    require_human_approval: bool = False
    auto_approve_threshold: float = 0.8


# Valid state transitions
TRANSITIONS = {
    RunState.QUEUED: [RunState.PLANNING, RunState.CANCELLED],
    RunState.PLANNING: [RunState.SPEC_REVIEW, RunState.IMPLEMENTING, RunState.FAILED],
    RunState.SPEC_REVIEW: [RunState.IMPLEMENTING, RunState.AWAITING_APPROVAL, RunState.FAILED],
    RunState.IMPLEMENTING: [RunState.TESTING, RunState.FAILED],
    RunState.TESTING: [RunState.REVIEWING, RunState.AWAITING_APPROVAL, RunState.COMPLETED, RunState.FAILED],
    RunState.REVIEWING: [RunState.COMPLETED, RunState.AWAITING_APPROVAL, RunState.FAILED],
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

    # Reviews
    review_results: List[Dict] = field(default_factory=list)  # [{gate, passed, issues, severity}]

    # Evidence
    evidence_log: List[Dict] = field(default_factory=list)  # [{task_id, evidence_type, content, timestamp}]

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
            "follow_up_runs": self.follow_up_runs,
            "created_at": self.created_at, "completed_at": self.completed_at,
        }
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False, default=str)

    @classmethod
    def from_result(cls, run_id: str, goal: str, result: Dict, trigger: str = "manual", trigger_ref: str = "") -> 'ProofBundle':
        """Create proof bundle from Swarm.run() result."""
        meta = result.get("metadata", {})
        results = result.get("results", {})

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

        tests_meta = meta.get("tests", {})
        approval_meta = meta.get("approval", {})

        return cls(
            run_id=run_id, goal=goal,
            trigger=trigger, trigger_ref=trigger_ref,
            tasks_completed=completed, tasks_failed=failed,
            total_tokens=meta.get("total_tokens", 0),
            total_cost_usd=meta.get("budget_spent_usd", 0),
            execution_time_s=meta.get("execution_time_s", 0),
            llm_calls=meta.get("llm_calls_used", 0),
            ontology_violations=[str(w) for w in meta.get("plan_quality", {}).get("ontology_warnings", [])],
            tests_run=tests_meta.get("run", 0),
            tests_passed=tests_meta.get("passed", 0),
            tests_failed=tests_meta.get("failed", 0),
            files_changed=meta.get("files_changed", []),
            artifacts=meta.get("artifacts", []),
            validation_summary=meta.get("validation_summary", ""),
            approval_status=approval_meta.get("status", "none"),
            approved_by=approval_meta.get("by", ""),
            approval_notes=approval_meta.get("notes", ""),
            skills_evolved=meta.get("skills_evolved", []),
            skills_promoted=meta.get("skills_promoted", []),
            next_steps=meta.get("next_steps", []),
            follow_up_runs=meta.get("follow_up_runs", []),
        )

    @classmethod
    def from_dict(cls, d: Dict) -> 'ProofBundle':
        """Restore a ProofBundle from a persisted dict (to_dict output)."""
        tests = d.get("tests", {})
        approval = d.get("approval", {})
        cost = d.get("cost", {})
        skills = d.get("skills", {})
        history = [
            StateTransition(
                from_state=t.get("from", ""), to_state=t.get("to", ""),
                reason=t.get("reason", ""), actor=t.get("actor", "system"),
                timestamp=t.get("timestamp", 0),
            )
            for t in d.get("state_history", [])
        ]
        return cls(
            run_id=d.get("run_id", ""), goal=d.get("goal", ""),
            trigger=d.get("trigger", ""), trigger_ref=d.get("trigger_ref", ""),
            state=d.get("state", "queued"), state_history=history,
            tasks_completed=d.get("tasks_completed", []),
            tasks_failed=d.get("tasks_failed", []),
            files_changed=d.get("files_changed", []),
            artifacts=d.get("artifacts", []),
            tests_run=tests.get("run", 0),
            tests_passed=tests.get("passed", 0),
            tests_failed=tests.get("failed", 0),
            validation_summary=d.get("validation_summary", ""),
            ontology_violations=d.get("ontology_violations", []),
            approval_status=approval.get("status", ""),
            approved_by=approval.get("by", ""),
            approval_notes=approval.get("notes", ""),
            total_tokens=cost.get("tokens", 0),
            total_cost_usd=cost.get("usd", 0),
            execution_time_s=cost.get("time_s", 0),
            llm_calls=cost.get("llm_calls", 0),
            skills_evolved=skills.get("evolved", []),
            skills_promoted=skills.get("promoted", []),
            next_steps=d.get("next_steps", []),
            follow_up_runs=d.get("follow_up_runs", []),
            created_at=d.get("created_at", 0),
            completed_at=d.get("completed_at", 0),
        )


@dataclass
class RunConfig:
    """Configuration for submitting a run."""
    goal: str = ""
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
    config: RunConfig = field(default_factory=RunConfig)
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

    def __init__(self, persist_dir: str = None, review_gates: List[ReviewGate] = None,
                 review_pipeline: Optional['_ReviewPipeline'] = None,
                 spec_gate: Optional[SpecGate] = None):
        self._runs: Dict[str, Run] = {}
        self._queue: List[str] = []  # Run IDs in priority order
        self._persist_dir = persist_dir
        self._on_state_change: List[Callable] = []
        self._review_gates = sorted(review_gates or [], key=lambda g: g.order)
        self._review_pipeline = review_pipeline
        self._spec_gate = spec_gate
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
        return len([r for r in self._queue
                    if self._runs[r].state in (RunState.QUEUED, RunState.RETRYING)])

    async def execute(self, run_id: str, swarm, approval_callback: Callable = None):
        """Execute a run through the full state machine (iterative, no recursion)."""
        run = self._runs.get(run_id)
        if not run:
            raise ValueError(f"Run not found: {run_id}")

        while True:
            try:
                # PLANNING
                self._transition(run, RunState.PLANNING, "Starting execution")

                # SPEC GATE — validate plan before implementation
                if self._spec_gate:
                    self._transition(run, RunState.SPEC_REVIEW, "Validating spec/plan")
                    plan_data = {"goal": run.config.goal, "tasks": run.config.tasks,
                                 "context": run.config.context}
                    passed, feedback = await self._spec_gate.validator(run.id, plan_data)
                    if not passed:
                        if self._spec_gate.require_human_approval:
                            self._transition(run, RunState.AWAITING_APPROVAL,
                                             f"Spec review failed, needs human approval: {feedback}")
                            run.proof.approval_status = "pending"
                            run.proof.completed_at = time.time()
                            self._persist_run(run)
                            return run.proof
                        else:
                            self._transition(run, RunState.FAILED,
                                             f"Spec review failed: {feedback}")
                            run.proof.completed_at = time.time()
                            self._persist_run(run)
                            return run.proof

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

                # REVIEWING — run review gates if configured
                if self._review_gates:
                    self._transition(run, RunState.REVIEWING, "entering review gates")
                    review_blocked = False
                    for gate in self._review_gates:
                        try:
                            result = await gate.reviewer(run.id, run.proof)
                        except Exception as exc:
                            result = ReviewResult(passed=False, issues=[f"Gate error: {exc}"], severity="critical")
                        run.proof.review_results.append({
                            "gate": gate.name, "passed": result.passed,
                            "issues": result.issues, "severity": result.severity,
                        })
                        if gate.required and not result.passed:
                            review_blocked = True
                            break
                    if review_blocked:
                        self._transition(run, RunState.AWAITING_APPROVAL,
                                         f"Review gate '{gate.name}' failed, needs review")
                        run.proof.approval_status = "pending"
                        if approval_callback:
                            approved = await approval_callback(run.id, run.proof.summary())
                            if approved:
                                run.proof.approval_status = "approved"
                                run.proof.approved_by = "callback"
                                self._transition(run, RunState.COMPLETED, "Approved after review failure")
                            else:
                                run.proof.approval_status = "rejected"
                                self._transition(run, RunState.REJECTED, "Rejected after review failure")
                        run.proof.completed_at = time.time()
                        self._persist_run(run)
                        return run.proof

                # Multi-stage review pipeline (if configured)
                if self._review_pipeline and _ReviewPipeline:
                    if run.state != RunState.REVIEWING:
                        self._transition(run, RunState.REVIEWING, "entering review pipeline")
                    pipeline_result = await self._review_pipeline.run(
                        run.id, run.proof, run.config.metadata
                    )
                    run.proof.review_results.append({
                        "pipeline": True,
                        "passed": pipeline_result.passed,
                        "score": pipeline_result.overall_score,
                        "stages_completed": pipeline_result.stages_completed,
                        "stages_total": pipeline_result.stages_total,
                        "escalated": pipeline_result.escalated,
                    })
                    if not pipeline_result.passed:
                        self._transition(run, RunState.FAILED, "Review pipeline failed")
                        run.proof.completed_at = time.time()
                        self._persist_run(run)
                        return run.proof

                has_failures = len(proof.tasks_failed) > 0
                should_retry = False

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
                                should_retry = True
                    # If no callback, stay in AWAITING_APPROVAL
                elif not has_failures:
                    self._transition(run, RunState.COMPLETED, f"{len(proof.tasks_completed)} tasks succeeded")
                else:
                    # Failures but no approval required — retry or fail
                    if run.retry_count < run.config.max_retries:
                        run.retry_count += 1
                        self._transition(run, RunState.RETRYING, f"Retry {run.retry_count}/{run.config.max_retries}")
                        should_retry = True
                    else:
                        self._transition(run, RunState.FAILED, f"{len(proof.tasks_failed)} tasks failed, retries exhausted")

                if should_retry:
                    continue  # Loop instead of recursive call

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
            self._persist_run(run)
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
                "config": {
                    "goal": run.config.goal, "trigger": run.config.trigger,
                    "trigger_ref": run.config.trigger_ref, "priority": run.config.priority,
                    "playbook": run.config.playbook, "pack": run.config.pack,
                    "context": run.config.context,
                    "requires_approval": run.config.requires_approval,
                    "max_retries": run.config.max_retries,
                    "workspace_id": run.config.workspace_id,
                    "metadata": run.config.metadata,
                },
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
                cfg = data["config"]
                config = RunConfig(
                    goal=cfg["goal"],
                    trigger=cfg.get("trigger", "manual"),
                    trigger_ref=cfg.get("trigger_ref", ""),
                    priority=cfg.get("priority", 5),
                    playbook=cfg.get("playbook", ""),
                    pack=cfg.get("pack", ""),
                    context=cfg.get("context", ""),
                    requires_approval=cfg.get("requires_approval", False),
                    max_retries=cfg.get("max_retries", 2),
                    workspace_id=cfg.get("workspace_id", ""),
                    metadata=cfg.get("metadata", {}),
                )
                proof_data = data.get("proof")
                proof = ProofBundle.from_dict(proof_data) if proof_data else ProofBundle()
                run = Run(id=data["id"], config=config,
                          state=RunState(data["state"]),
                          proof=proof,
                          retry_count=data.get("retry_count", 0),
                          created_at=data.get("created_at", 0))
                self._runs[run.id] = run
                if run.state == RunState.RETRYING:
                    self._queue.append(run.id)
            except Exception as exc:
                logger.warning("Failed to load run from %s: %s", fname, exc)
