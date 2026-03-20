"""Tests for agent_swarm.ship — Ship Pipeline."""
import asyncio
import pytest
from agent_swarm.ship import (
    ShipStage, ShipStatus, ShipCheckpoint, ShipConfig,
    ShipResult, ShipPipeline,
)


# -- Enum values --

def test_ship_stage_values():
    assert ShipStage.TEST.value == "test"
    assert ShipStage.REVIEW.value == "review"
    assert ShipStage.VERSION.value == "version"
    assert ShipStage.CHANGELOG.value == "changelog"
    assert ShipStage.COMMIT.value == "commit"
    assert ShipStage.PUSH.value == "push"


def test_ship_status_values():
    assert ShipStatus.PENDING.value == "pending"
    assert ShipStatus.RUNNING.value == "running"
    assert ShipStatus.PASSED.value == "passed"
    assert ShipStatus.FAILED.value == "failed"
    assert ShipStatus.SKIPPED.value == "skipped"


# -- ShipConfig defaults --

def test_ship_config_defaults():
    cfg = ShipConfig()
    assert cfg.test_cmd == "pytest tests/ -q"
    assert cfg.review_enabled is True
    assert cfg.version_bump == "patch"
    assert cfg.changelog_enabled is True
    assert cfg.push_remote == "origin"
    assert cfg.push_branch == "main"
    assert cfg.dry_run is False
    assert cfg.review_pipeline is None
    assert cfg.safety_guards is None


# -- ShipCheckpoint --

def test_ship_checkpoint_creation():
    cp = ShipCheckpoint(stage=ShipStage.TEST)
    assert cp.stage == ShipStage.TEST
    assert cp.status == ShipStatus.PENDING
    assert cp.output == ""
    assert cp.error == ""


# -- ShipResult --

def test_ship_result_completed_stages():
    result = ShipResult(checkpoints=[
        ShipCheckpoint(stage=ShipStage.TEST, status=ShipStatus.PASSED),
        ShipCheckpoint(stage=ShipStage.REVIEW, status=ShipStatus.SKIPPED),
        ShipCheckpoint(stage=ShipStage.VERSION, status=ShipStatus.PASSED),
    ])
    assert result.completed_stages == 2
    assert result.total_stages == 3


def test_ship_result_get_checkpoint():
    cp = ShipCheckpoint(stage=ShipStage.COMMIT, status=ShipStatus.PASSED)
    result = ShipResult(checkpoints=[cp])
    assert result.get_checkpoint(ShipStage.COMMIT) is cp
    assert result.get_checkpoint(ShipStage.PUSH) is None


def test_ship_result_format_summary_success():
    result = ShipResult(
        success=True,
        version="1.2.3",
        checkpoints=[
            ShipCheckpoint(stage=ShipStage.TEST, status=ShipStatus.PASSED),
            ShipCheckpoint(stage=ShipStage.REVIEW, status=ShipStatus.SKIPPED),
        ],
    )
    summary = result.format_summary()
    assert "SUCCESS" in summary
    assert "1.2.3" in summary


def test_ship_result_format_summary_dry_run():
    result = ShipResult(success=True, dry_run=True, checkpoints=[])
    summary = result.format_summary()
    assert "dry run" in summary


# -- Async helpers --

async def mock_handler(config, stage):
    return f"{stage.value}_done"


async def failing_handler(config, stage):
    raise RuntimeError(f"{stage.value} exploded")


async def version_handler(config, stage):
    return "2.0.0"


def _run(coro):
    return asyncio.run(coro)


# -- ShipPipeline.run --

def test_pipeline_run_all_pass():
    handlers = {s: mock_handler for s in ShipPipeline.STAGE_ORDER}
    pipeline = ShipPipeline(stage_handlers=handlers)
    result = _run(pipeline.run())
    assert result.success is True
    assert result.completed_stages == 6
    assert all(cp.status == ShipStatus.PASSED for cp in result.checkpoints)


def test_pipeline_run_stage_failure():
    handlers = {s: mock_handler for s in ShipPipeline.STAGE_ORDER}
    handlers[ShipStage.VERSION] = failing_handler
    pipeline = ShipPipeline(stage_handlers=handlers)
    result = _run(pipeline.run())
    assert result.success is False
    assert "version" in result.error
    version_cp = result.get_checkpoint(ShipStage.VERSION)
    assert version_cp.status == ShipStatus.FAILED


def test_pipeline_run_review_disabled():
    cfg = ShipConfig(review_enabled=False)
    handlers = {s: mock_handler for s in ShipPipeline.STAGE_ORDER}
    pipeline = ShipPipeline(config=cfg, stage_handlers=handlers)
    result = _run(pipeline.run())
    assert result.success is True
    review_cp = result.get_checkpoint(ShipStage.REVIEW)
    assert review_cp.status == ShipStatus.SKIPPED


def test_pipeline_run_dry_run():
    cfg = ShipConfig(dry_run=True)
    handlers = {s: mock_handler for s in ShipPipeline.STAGE_ORDER}
    pipeline = ShipPipeline(config=cfg, stage_handlers=handlers)
    result = _run(pipeline.run())
    assert result.success is True
    assert result.dry_run is True
    for cp in result.checkpoints:
        if cp.status == ShipStatus.PASSED:
            assert "[dry run]" in cp.output


def test_pipeline_run_no_handlers():
    pipeline = ShipPipeline()
    result = _run(pipeline.run())
    assert result.success is True
    assert all(cp.status in (ShipStatus.PASSED, ShipStatus.SKIPPED) for cp in result.checkpoints)


def test_pipeline_run_tracks_version():
    handlers = {s: mock_handler for s in ShipPipeline.STAGE_ORDER}
    handlers[ShipStage.VERSION] = version_handler
    pipeline = ShipPipeline(stage_handlers=handlers)
    result = _run(pipeline.run())
    assert result.version == "2.0.0"


# -- ShipPipeline.resume --

def test_pipeline_resume_from_middle():
    async def _resume_scenario():
        handlers = {s: mock_handler for s in ShipPipeline.STAGE_ORDER}
        pipeline = ShipPipeline(stage_handlers=handlers)
        # Run full first to populate checkpoints
        await pipeline.run()
        # Resume from COMMIT
        result = await pipeline.resume(ShipStage.COMMIT)
        return result

    result = _run(_resume_scenario())
    assert result.success is True
    # Should have checkpoints for all stages
    assert len(result.checkpoints) == 6
