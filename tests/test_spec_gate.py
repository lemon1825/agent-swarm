"""Tests for SpecGate integration with RunMachine."""
import asyncio
import pytest
from agent_swarm.run_machine import RunState, RunMachine, RunConfig, SpecGate


def test_spec_gate_dataclass_defaults():
    gate = SpecGate(validator=lambda rid, plan: (True, "ok"))
    assert gate.require_human_approval is False
    assert gate.auto_approve_threshold == 0.8
    assert callable(gate.validator)


def test_run_state_spec_review_exists():
    assert RunState.SPEC_REVIEW == "spec_review"
    assert RunState.SPEC_REVIEW.value == "spec_review"


def test_run_machine_no_spec_gate():
    machine = RunMachine()
    assert machine._spec_gate is None


def test_run_machine_with_spec_gate():
    gate = SpecGate(validator=lambda rid, plan: (True, "ok"))
    machine = RunMachine(spec_gate=gate)
    assert machine._spec_gate is gate


@pytest.mark.asyncio
async def test_spec_gate_pass_transitions_to_implementing():
    async def passing_validator(run_id, plan):
        return (True, "looks good")

    gate = SpecGate(validator=passing_validator)
    machine = RunMachine(spec_gate=gate)

    class MockSwarm:
        async def run(self, goal, tasks=None, context="", playbook=None):
            return {
                "metadata": {"total_tokens": 0, "budget_spent_usd": 0,
                             "execution_time_s": 0, "llm_calls_used": 0,
                             "tests": {"run": 1, "passed": 1, "failed": 0},
                             "plan_quality": {}},
                "results": {},
            }

    config = RunConfig(goal="Test goal")
    run_id = machine.submit(config)
    proof = await machine.execute(run_id, MockSwarm())

    states = [t.to_state for t in proof.state_history]
    assert "spec_review" in states
    assert "implementing" in states
    assert proof.state == "completed"


@pytest.mark.asyncio
async def test_spec_gate_fail_transitions_to_failed():
    async def failing_validator(run_id, plan):
        return (False, "spec has issues")

    gate = SpecGate(validator=failing_validator)
    machine = RunMachine(spec_gate=gate)

    config = RunConfig(goal="Test goal")
    run_id = machine.submit(config)

    class MockSwarm:
        pass

    proof = await machine.execute(run_id, MockSwarm())

    states = [t.to_state for t in proof.state_history]
    assert "spec_review" in states
    assert "failed" in states
    assert "implementing" not in states
    assert proof.state == "failed"


@pytest.mark.asyncio
async def test_spec_gate_fail_with_human_approval():
    async def failing_validator(run_id, plan):
        return (False, "needs human review")

    gate = SpecGate(validator=failing_validator, require_human_approval=True)
    machine = RunMachine(spec_gate=gate)

    config = RunConfig(goal="Test goal")
    run_id = machine.submit(config)

    class MockSwarm:
        pass

    proof = await machine.execute(run_id, MockSwarm())

    states = [t.to_state for t in proof.state_history]
    assert "spec_review" in states
    assert "awaiting_approval" in states
    assert "implementing" not in states
    assert proof.state == "awaiting_approval"
    assert proof.approval_status == "pending"
