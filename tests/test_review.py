"""Tests for agent_swarm.review — Multi-Stage Review Pipeline."""
import asyncio
import pytest

from agent_swarm.review import (
    ReviewPipeline,
    ReviewPipelineResult,
    ReviewResult,
    ReviewRole,
    ReviewStage,
)
from agent_swarm.convergence import ConvergenceConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_reviewer(role, passed=True, score=0.9, feedback="", issues=None):
    """Create an async reviewer function that returns a fixed ReviewResult."""
    async def reviewer(run_id, proof, context):
        return ReviewResult(
            role=role, passed=passed, score=score,
            feedback=feedback, issues=issues or [],
        )
    return reviewer


def _make_failing_then_passing_reviewer(role, fail_count=1):
    """Reviewer that fails `fail_count` times then passes."""
    call_count = {"n": 0}

    async def reviewer(run_id, proof, context):
        call_count["n"] += 1
        if call_count["n"] <= fail_count:
            return ReviewResult(role=role, passed=False, score=0.3, feedback="needs work")
        return ReviewResult(role=role, passed=True, score=0.9)

    return reviewer


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestReviewRole:
    def test_enum_values(self):
        assert ReviewRole.SPEC_COMPLIANCE.value == "spec_compliance"
        assert ReviewRole.CODE_QUALITY.value == "code_quality"
        assert ReviewRole.SECURITY.value == "security"
        assert ReviewRole.DESIGN.value == "design"
        assert ReviewRole.CEO.value == "ceo"
        assert ReviewRole.ENGINEERING.value == "engineering"

    def test_enum_members_count(self):
        assert len(ReviewRole) == 6


class TestReviewStage:
    def test_defaults(self):
        stage = ReviewStage(name="s1", gates=[ReviewRole.SECURITY])
        assert stage.pass_threshold == 0.7
        assert stage.max_iterations == 3
        assert stage.skip_condition is None
        assert stage.require_all_pass is False

    def test_custom_values(self):
        stage = ReviewStage(
            name="strict",
            gates=[ReviewRole.CEO, ReviewRole.ENGINEERING],
            pass_threshold=0.9,
            max_iterations=1,
            require_all_pass=True,
        )
        assert stage.pass_threshold == 0.9
        assert stage.max_iterations == 1
        assert stage.require_all_pass is True


class TestReviewPipelineResult:
    def test_overall_score_empty(self):
        r = ReviewPipelineResult(passed=True, stages_completed=0, stages_total=0)
        assert r.overall_score == 0.0

    def test_overall_score_computed(self):
        r = ReviewPipelineResult(
            passed=True, stages_completed=1, stages_total=1,
            stage_results={
                "s1": [
                    ReviewResult(role=ReviewRole.SECURITY, passed=True, score=0.8),
                    ReviewResult(role=ReviewRole.CODE_QUALITY, passed=True, score=1.0),
                ],
            },
        )
        assert r.overall_score == pytest.approx(0.9)

    def test_overall_score_multi_stage(self):
        r = ReviewPipelineResult(
            passed=True, stages_completed=2, stages_total=2,
            stage_results={
                "s1": [ReviewResult(role=ReviewRole.SECURITY, passed=True, score=0.6)],
                "s2": [ReviewResult(role=ReviewRole.CEO, passed=True, score=1.0)],
            },
        )
        assert r.overall_score == pytest.approx(0.8)


class TestReviewPipelineAllPass:
    @pytest.mark.asyncio
    async def test_all_stages_pass(self):
        stages = [
            ReviewStage(name="stage1", gates=[ReviewRole.SPEC_COMPLIANCE, ReviewRole.CODE_QUALITY]),
            ReviewStage(name="stage2", gates=[ReviewRole.SECURITY]),
        ]
        reviewers = {
            ReviewRole.SPEC_COMPLIANCE: _make_reviewer(ReviewRole.SPEC_COMPLIANCE),
            ReviewRole.CODE_QUALITY: _make_reviewer(ReviewRole.CODE_QUALITY),
            ReviewRole.SECURITY: _make_reviewer(ReviewRole.SECURITY),
        }
        pipeline = ReviewPipeline(stages=stages, reviewers=reviewers)
        result = await pipeline.run("run_1", proof={"data": "test"})

        assert result.passed is True
        assert result.stages_completed == 2
        assert result.stages_total == 2
        assert not result.escalated


class TestReviewPipelineFail:
    @pytest.mark.asyncio
    async def test_stage_fails(self):
        stages = [
            ReviewStage(name="strict", gates=[ReviewRole.SECURITY], pass_threshold=0.8, max_iterations=1),
        ]
        reviewers = {
            ReviewRole.SECURITY: _make_reviewer(ReviewRole.SECURITY, passed=False, score=0.2),
        }
        pipeline = ReviewPipeline(stages=stages, reviewers=reviewers)
        result = await pipeline.run("run_2", proof={})

        assert result.passed is False
        assert result.stages_completed == 0


class TestReviewPipelineSkip:
    @pytest.mark.asyncio
    async def test_skip_condition(self):
        stages = [
            ReviewStage(
                name="skippable",
                gates=[ReviewRole.DESIGN],
                skip_condition=lambda ctx: ctx.get("skip_design", False),
            ),
            ReviewStage(name="required", gates=[ReviewRole.SECURITY]),
        ]
        reviewers = {
            ReviewRole.DESIGN: _make_reviewer(ReviewRole.DESIGN, passed=False, score=0.0),
            ReviewRole.SECURITY: _make_reviewer(ReviewRole.SECURITY),
        }
        pipeline = ReviewPipeline(stages=stages, reviewers=reviewers)
        result = await pipeline.run("run_3", proof={}, context={"skip_design": True})

        assert result.passed is True
        assert result.stages_completed == 2
        assert "skippable" not in result.stage_results


class TestReviewPipelineRetry:
    @pytest.mark.asyncio
    async def test_retry_then_pass(self):
        stages = [
            ReviewStage(name="retry_stage", gates=[ReviewRole.CODE_QUALITY], max_iterations=3),
        ]
        reviewers = {
            ReviewRole.CODE_QUALITY: _make_failing_then_passing_reviewer(ReviewRole.CODE_QUALITY, fail_count=2),
        }
        pipeline = ReviewPipeline(stages=stages, reviewers=reviewers)
        result = await pipeline.run("run_4", proof={})

        assert result.passed is True
        assert result.stages_completed == 1


class TestReviewPipelineEscalation:
    @pytest.mark.asyncio
    async def test_escalation_approved(self):
        stages = [
            ReviewStage(name="failing", gates=[ReviewRole.CEO], max_iterations=1, pass_threshold=0.9),
        ]
        reviewers = {
            ReviewRole.CEO: _make_reviewer(ReviewRole.CEO, passed=False, score=0.3),
        }

        async def approve_escalation(run_id, stage_name, results):
            return True

        pipeline = ReviewPipeline(stages=stages, reviewers=reviewers, escalation_callback=approve_escalation)
        result = await pipeline.run("run_5", proof={})

        assert result.passed is True  # escalation overrides failure
        assert result.escalated is True
        assert "approved" in result.escalation_reason

    @pytest.mark.asyncio
    async def test_escalation_rejected(self):
        stages = [
            ReviewStage(name="failing", gates=[ReviewRole.CEO], max_iterations=1, pass_threshold=0.9),
        ]
        reviewers = {
            ReviewRole.CEO: _make_reviewer(ReviewRole.CEO, passed=False, score=0.3),
        }

        async def reject_escalation(run_id, stage_name, results):
            return False

        pipeline = ReviewPipeline(stages=stages, reviewers=reviewers, escalation_callback=reject_escalation)
        result = await pipeline.run("run_6", proof={})

        assert result.passed is False
        assert result.escalated is True
        assert "rejected" in result.escalation_reason


class TestReviewPipelineRequireAllPass:
    @pytest.mark.asyncio
    async def test_require_all_pass_fails_when_one_fails(self):
        stages = [
            ReviewStage(
                name="all_must_pass",
                gates=[ReviewRole.SECURITY, ReviewRole.CODE_QUALITY],
                require_all_pass=True,
                max_iterations=1,
            ),
        ]
        reviewers = {
            ReviewRole.SECURITY: _make_reviewer(ReviewRole.SECURITY, passed=True, score=0.9),
            ReviewRole.CODE_QUALITY: _make_reviewer(ReviewRole.CODE_QUALITY, passed=False, score=0.8),
        }
        pipeline = ReviewPipeline(stages=stages, reviewers=reviewers)
        result = await pipeline.run("run_7", proof={})

        assert result.passed is False

    @pytest.mark.asyncio
    async def test_require_all_pass_succeeds_when_all_pass(self):
        stages = [
            ReviewStage(
                name="all_must_pass",
                gates=[ReviewRole.SECURITY, ReviewRole.CODE_QUALITY],
                require_all_pass=True,
                max_iterations=1,
            ),
        ]
        reviewers = {
            ReviewRole.SECURITY: _make_reviewer(ReviewRole.SECURITY, passed=True, score=0.9),
            ReviewRole.CODE_QUALITY: _make_reviewer(ReviewRole.CODE_QUALITY, passed=True, score=0.8),
        }
        pipeline = ReviewPipeline(stages=stages, reviewers=reviewers)
        result = await pipeline.run("run_8", proof={})

        assert result.passed is True


class TestReviewPipelineEmpty:
    @pytest.mark.asyncio
    async def test_empty_pipeline(self):
        pipeline = ReviewPipeline(stages=[], reviewers={})
        result = await pipeline.run("run_9", proof={})

        assert result.passed is True
        assert result.stages_completed == 0
        assert result.stages_total == 0
        assert result.overall_score == 0.0

    @pytest.mark.asyncio
    async def test_stage_with_no_matching_reviewers(self):
        stages = [
            ReviewStage(name="orphan", gates=[ReviewRole.DESIGN]),
        ]
        pipeline = ReviewPipeline(stages=stages, reviewers={})
        result = await pipeline.run("run_10", proof={})

        assert result.passed is True
        assert result.stages_completed == 1


# ---------------------------------------------------------------------------
# Convergence Integration Tests (HRM)
# ---------------------------------------------------------------------------

class TestReviewConvergence:
    """Tests for HRM-style convergence-gated review iteration."""

    @pytest.mark.asyncio
    async def test_convergence_stops_stable_scores(self):
        """When scores stabilize, iteration should stop before max_iterations."""
        call_count = {"n": 0}

        async def stable_reviewer(run_id, proof, context):
            call_count["n"] += 1
            return ReviewResult(
                role=ReviewRole.CODE_QUALITY, passed=False,
                score=0.6, feedback="needs work",
            )

        stages = [
            ReviewStage(
                name="quality",
                gates=[ReviewRole.CODE_QUALITY],
                pass_threshold=0.9,  # will never pass
                max_iterations=10,
                convergence=ConvergenceConfig(
                    stability_threshold=0.05,
                    min_iterations=2,
                    score_history_window=3,
                ),
            ),
        ]
        pipeline = ReviewPipeline(
            stages=stages,
            reviewers={ReviewRole.CODE_QUALITY: stable_reviewer},
        )
        result = await pipeline.run("conv_run", proof={})
        # Should stop early due to convergence (scores are always 0.6)
        assert call_count["n"] < 10

    @pytest.mark.asyncio
    async def test_no_convergence_uses_max_iterations(self):
        """Without convergence config, standard max_iterations behavior."""
        call_count = {"n": 0}

        async def reviewer(run_id, proof, context):
            call_count["n"] += 1
            return ReviewResult(
                role=ReviewRole.SECURITY, passed=False,
                score=0.3, feedback="fail",
            )

        stages = [
            ReviewStage(
                name="sec",
                gates=[ReviewRole.SECURITY],
                pass_threshold=0.9,
                max_iterations=3,
                # no convergence config
            ),
        ]
        pipeline = ReviewPipeline(
            stages=stages,
            reviewers={ReviewRole.SECURITY: reviewer},
        )
        result = await pipeline.run("noconv", proof={})
        assert call_count["n"] == 3
        assert result.passed is False

    @pytest.mark.asyncio
    async def test_convergence_config_on_stage(self):
        """Verify ConvergenceConfig can be set on ReviewStage."""
        cfg = ConvergenceConfig(max_iterations=5, stability_threshold=0.1)
        stage = ReviewStage(
            name="test",
            gates=[ReviewRole.CODE_QUALITY],
            convergence=cfg,
        )
        assert stage.convergence is cfg
        assert stage.convergence.stability_threshold == 0.1
