"""Ship Pipeline for Agent Swarm.

Checkpoint-based pipeline: test -> review -> version -> changelog -> commit -> push.
Inspired by gstack ship skill.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Awaitable


class ShipStage(Enum):
    TEST = "test"
    REVIEW = "review"
    VERSION = "version"
    CHANGELOG = "changelog"
    COMMIT = "commit"
    PUSH = "push"


class ShipStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ShipCheckpoint:
    stage: ShipStage
    status: ShipStatus = ShipStatus.PENDING
    output: str = ""
    error: str = ""
    timestamp: float = 0.0
    duration_ms: float = 0.0


@dataclass
class ShipConfig:
    """Configuration for the ship pipeline."""
    test_cmd: str = "pytest tests/ -q"
    review_enabled: bool = True
    version_bump: str = "patch"  # patch, minor, major
    changelog_enabled: bool = True
    commit_msg_template: str = "release: v{version}"
    push_remote: str = "origin"
    push_branch: str = "main"
    dry_run: bool = False

    # Optional integrations
    review_pipeline: Optional[Any] = None  # ReviewPipeline instance
    safety_guards: Optional[Any] = None  # GuardChain or similar


@dataclass
class ShipResult:
    """Result of a ship pipeline execution."""
    success: bool = False
    checkpoints: List[ShipCheckpoint] = field(default_factory=list)
    version: str = ""
    error: str = ""
    dry_run: bool = False

    @property
    def completed_stages(self) -> int:
        return sum(1 for c in self.checkpoints if c.status == ShipStatus.PASSED)

    @property
    def total_stages(self) -> int:
        return len(self.checkpoints)

    def get_checkpoint(self, stage: ShipStage) -> Optional[ShipCheckpoint]:
        for c in self.checkpoints:
            if c.stage == stage:
                return c
        return None

    def format_summary(self) -> str:
        lines = [f"Ship {'(dry run) ' if self.dry_run else ''}— {'SUCCESS' if self.success else 'FAILED'}"]
        if self.version:
            lines.append(f"Version: {self.version}")
        for cp in self.checkpoints:
            icon = (
                "✓" if cp.status == ShipStatus.PASSED
                else ("✗" if cp.status == ShipStatus.FAILED
                      else ("⊘" if cp.status == ShipStatus.SKIPPED else "…"))
            )
            lines.append(f"  {icon} {cp.stage.value}: {cp.status.value}")
            if cp.error:
                lines.append(f"    Error: {cp.error}")
        if self.error:
            lines.append(f"Error: {self.error}")
        return "\n".join(lines)


class ShipPipeline:
    """Checkpoint-based ship pipeline with resume capability."""

    # Default stage order
    STAGE_ORDER = [
        ShipStage.TEST, ShipStage.REVIEW, ShipStage.VERSION,
        ShipStage.CHANGELOG, ShipStage.COMMIT, ShipStage.PUSH,
    ]

    def __init__(
        self,
        config: Optional[ShipConfig] = None,
        stage_handlers: Optional[Dict[ShipStage, Callable[..., Awaitable[str]]]] = None,
    ):
        self._config = config or ShipConfig()
        self._handlers = stage_handlers or {}
        self._checkpoints: List[ShipCheckpoint] = []

    async def run(self) -> ShipResult:
        """Execute all stages sequentially with checkpoints."""
        result = ShipResult(dry_run=self._config.dry_run)

        for stage in self.STAGE_ORDER:
            # Skip review if disabled
            if stage == ShipStage.REVIEW and not self._config.review_enabled:
                cp = ShipCheckpoint(stage=stage, status=ShipStatus.SKIPPED, timestamp=time.time())
                result.checkpoints.append(cp)
                continue

            # Skip changelog if disabled
            if stage == ShipStage.CHANGELOG and not self._config.changelog_enabled:
                cp = ShipCheckpoint(stage=stage, status=ShipStatus.SKIPPED, timestamp=time.time())
                result.checkpoints.append(cp)
                continue

            # Safety check before commit/push
            if stage in (ShipStage.COMMIT, ShipStage.PUSH) and self._config.safety_guards:
                from .safety import GuardAction
                guard_result = self._config.safety_guards.check(
                    f"{stage.value} {self._config.push_remote} {self._config.push_branch}"
                )
                if guard_result.action == GuardAction.BLOCK:
                    cp = ShipCheckpoint(
                        stage=stage,
                        status=ShipStatus.FAILED,
                        error=f"Blocked: {guard_result.reason}",
                        timestamp=time.time(),
                    )
                    result.checkpoints.append(cp)
                    result.error = f"Safety guard blocked {stage.value}"
                    return result

            cp = await self._execute_stage(stage)
            result.checkpoints.append(cp)
            self._checkpoints.append(cp)

            if cp.status == ShipStatus.FAILED:
                result.error = f"Stage {stage.value} failed: {cp.error}"
                return result

            # Track version
            if stage == ShipStage.VERSION and cp.output:
                result.version = cp.output

        result.success = True
        return result

    async def resume(self, from_stage: ShipStage) -> ShipResult:
        """Resume pipeline from a specific stage."""
        result = ShipResult(dry_run=self._config.dry_run)

        # Copy existing checkpoints up to from_stage
        started = False
        for stage in self.STAGE_ORDER:
            if stage == from_stage:
                started = True
            if not started:
                # Find existing checkpoint
                existing = None
                for cp in self._checkpoints:
                    if cp.stage == stage:
                        existing = cp
                        break
                if existing:
                    result.checkpoints.append(existing)
                continue

            cp = await self._execute_stage(stage)
            result.checkpoints.append(cp)
            if cp.status == ShipStatus.FAILED:
                result.error = f"Stage {stage.value} failed: {cp.error}"
                return result
            if stage == ShipStage.VERSION and cp.output:
                result.version = cp.output

        result.success = True
        return result

    async def _execute_stage(self, stage: ShipStage) -> ShipCheckpoint:
        """Execute a single stage."""
        cp = ShipCheckpoint(stage=stage, status=ShipStatus.RUNNING, timestamp=time.time())
        start = time.time()

        handler = self._handlers.get(stage)
        if handler:
            try:
                if self._config.dry_run:
                    cp.output = f"[dry run] {stage.value}"
                    cp.status = ShipStatus.PASSED
                else:
                    output = await handler(self._config, stage)
                    cp.output = str(output) if output else ""
                    cp.status = ShipStatus.PASSED
            except Exception as exc:
                cp.error = str(exc)
                cp.status = ShipStatus.FAILED
        else:
            # No handler = auto-pass (useful for testing)
            cp.output = f"No handler for {stage.value}"
            cp.status = ShipStatus.PASSED

        cp.duration_ms = (time.time() - start) * 1000
        return cp
