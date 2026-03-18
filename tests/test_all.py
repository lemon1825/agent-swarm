from agent_swarm import Run, RunConfig, Swarm
from agent_swarm.core import TaskResult
from agent_swarm.run_machine import ProofBundle


def test_public_api_imports_swarm():
    assert Swarm.__name__ == "Swarm"


def test_run_can_be_instantiated_without_explicit_config():
    run = Run()

    assert isinstance(run.config, RunConfig)
    assert run.config.goal == ""
    assert run.proof.run_id == ""


def test_proof_bundle_from_result_captures_extended_metadata():
    result = {
        "results": {
            "research": TaskResult(
                index=0,
                task_id="research",
                role="Researcher",
                agent_name="Researcher#research",
                output="Collect evidence",
                duration_ms=1200,
                attempts=2,
                tokens_used=321,
            ),
            "review": TaskResult(
                index=1,
                task_id="review",
                role="Reviewer",
                agent_name="Reviewer#review",
                validation_failures=["missing citation"],
                duration_ms=800,
                attempts=1,
                tokens_used=111,
            ),
        },
        "metadata": {
            "total_tokens": 432,
            "budget_spent_usd": 1.25,
            "execution_time_s": 3.5,
            "llm_calls_used": 4,
            "plan_quality": {"ontology_warnings": ["warn: reviewer mismatch"]},
            "next_steps": ["approve", "rerun"],
            "follow_up_runs": ["run_002"],
            "files_changed": ["report.md"],
            "artifacts": [{"name": "trace.json", "type": ".json"}],
            "tests": {"run": 3, "passed": 2, "failed": 1},
            "approval": {"status": "pending", "by": "lead", "notes": "Need sign-off"},
            "validation_summary": "1 validation warning",
            "skills_evolved": ["review-pack"],
            "skills_promoted": ["research-pack"],
        },
    }

    proof = ProofBundle.from_result("run_001", "Ship review workflow", result, "github", "issue#10")

    assert proof.run_id == "run_001"
    assert proof.goal == "Ship review workflow"
    assert proof.trigger == "github"
    assert proof.trigger_ref == "issue#10"
    assert proof.tests_run == 3
    assert proof.tests_passed == 2
    assert proof.tests_failed == 1
    assert proof.files_changed == ["report.md"]
    assert proof.artifacts == [{"name": "trace.json", "type": ".json"}]
    assert proof.approval_status == "pending"
    assert proof.approved_by == "lead"
    assert proof.approval_notes == "Need sign-off"
    assert proof.validation_summary == "1 validation warning"
    assert proof.skills_evolved == ["review-pack"]
    assert proof.skills_promoted == ["research-pack"]
    assert proof.follow_up_runs == ["run_002"]
    assert proof.next_steps == ["approve", "rerun"]
    assert proof.ontology_violations == ["warn: reviewer mismatch"]
    assert proof.tasks_completed[0]["output_preview"] == "Collect evidence"
    assert proof.tasks_failed[0]["error"] == "missing citation"
