"""Example 08: Operational Pipeline — event-triggered autonomous execution.

Shows the full Symphony-inspired flow:
  Webhook → Tracker → RunMachine → Workspace → Swarm → ProofBundle

Run: python examples/08_operational_pipeline.py
"""
import asyncio
from agent_swarm import (
    Swarm, SubTask, RunMachine, RunConfig, RunState, ProofBundle,
    WorkspaceManager, TrackerAdapter, Supervisor, SupervisorConfig,
    MemoryStore, DetailedTracer, DurableCheckpoint,
    LLMCache, cached_llm, SmartRouter,
    ToolRegistry, SAFE_TOOLS,
)

# --- Mock LLM ---
async def mock_llm(prompt, tools=None):
    return f"Completed: {prompt[:50]}..."

async def main():
    # 1. Setup operational components
    machine = RunMachine()
    tracker = TrackerAdapter(machine)
    memory = MemoryStore()  # defaults to ~/.agent-swarm/memory
    tracer = DetailedTracer()
    cache = LLMCache(max_size=100, ttl_seconds=300)
    llm = cached_llm(mock_llm, cache)

    print("=== Agent Swarm — Operational Pipeline ===\n")

    # 2. Simulate GitHub webhook
    print("1. GitHub webhook received (issue #42 labeled 'ready')...")
    run_id = tracker.handle_webhook({
        "action": "labeled",
        "label": {"name": "ready"},
        "issue": {
            "number": 42,
            "title": "Fix authentication timeout",
            "body": "Login fails after 30s. Need to increase timeout and add retry.",
            "labels": [{"name": "ready"}, {"name": "bug"}],
            "html_url": "https://github.com/example/repo/issues/42",
            "user": {"login": "developer"},
        },
    })
    print(f"   Run created: {run_id}")
    print(f"   State: {machine.get(run_id).state.value}")

    # 3. Execute through state machine
    print("\n2. Executing run through state machine...")
    swarm = Swarm(llm=llm, event_bus=tracer.as_event_bus())

    proof = await machine.execute(run_id, swarm)

    # 4. Results
    run = machine.get(run_id)
    print(f"   Final state: {run.state.value}")
    print(f"   Tasks completed: {len(proof.tasks_completed)}")
    print(f"   Trigger: {proof.trigger} ({proof.trigger_ref})")

    # 5. Proof bundle
    print(f"\n3. Proof Bundle:")
    print(proof.summary())

    # 6. Trace
    trace = tracer.get_trace()
    print(f"\n4. Trace: {trace.tasks_succeeded} succeeded, {trace.tasks_failed} failed")

    # 7. Memory
    memory.add("long", f"Issue #{42}: auth timeout fix applied", tags=["auth", "fix"])
    memory.add("context", "Auth timeout should be 60s minimum", skill="AuthReview")
    print(f"\n5. Memory: {memory.stats()['total']} entries stored")

    # 8. Cache stats
    print(f"6. Cache: {cache.stats()}")

    print("\n=== Pipeline complete ✓ ===")

if __name__ == "__main__":
    asyncio.run(main())
