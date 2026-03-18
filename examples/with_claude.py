"""Example: Connect to Anthropic Claude.

Setup:
    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...

Run:
    python examples/with_claude.py
"""
import asyncio
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_swarm import (
    Swarm, SubTask, BudgetPolicy, GoalAncestry,
    OntologyRegistry, OntologyGateMode, CORE_ONTOLOGY,
    SkillBank, Skill, SkillManifest, SCHEMA_PRESETS, MultiValidator,
)

async def claude_llm(prompt: str, tools=None) -> str:
    """Call Claude API. Agent Swarm handles timeout, retry, rate limit automatically."""
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        print("Install anthropic: pip install anthropic")
        raise

    client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text

async def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY environment variable first.")
        print("  export ANTHROPIC_API_KEY=sk-ant-...")
        return

    # Full production setup: ontology + budget + schema validation + goal ancestry
    registry = OntologyRegistry([CORE_ONTOLOGY])

    bank = SkillBank()
    bank.add(Skill(name="WebSearch", principle="Find and synthesize sources",
                   when_to_apply="research, investigation",
                   manifest=SkillManifest(capabilities=["sw:SkillCap/WebSearch"],
                                          task_types=["sw:TaskType/Research"])))
    bank.add(Skill(name="DataAnalysis", principle="Analyze data and patterns",
                   when_to_apply="analysis, comparison",
                   manifest=SkillManifest(capabilities=["sw:SkillCap/DataAnalysis"],
                                          task_types=["sw:TaskType/Analysis"])))
    bank.add(Skill(name="TextGen", principle="Generate written content",
                   when_to_apply="writing, report",
                   manifest=SkillManifest(capabilities=["sw:SkillCap/TextGeneration"],
                                          task_types=["sw:TaskType/Writing"])))

    swarm = Swarm(
        llm=claude_llm,
        ontology=registry,
        ontology_gate_mode=OntologyGateMode.WARN,
        skill_bank=bank,
        budget_policy=BudgetPolicy(max_cost_per_run=1.00, block_on_exceed=True),
        goal_ancestry=GoalAncestry(mission="Build the best AI agent engine"),
    )

    # Run with playbook
    print("=== Running Product Discovery with Claude ===\n")
    result = await swarm.run(
        goal="Explore opportunities in the AI developer tools market",
        playbook="discover",
    )

    print("=== Results ===")
    for tid, r in result["results"].items():
        status = "✓" if r.success else "✗"
        print(f"  {status} [{r.role}] {(r.output or r.error or '')[:100]}...")

    meta = result["metadata"]
    print(f"\n--- {meta['succeeded']}/{meta['total_tasks']} tasks, {meta['execution_time_s']}s, ${meta['budget_spent_usd']:.4f} ---")
    if meta.get("next_steps"):
        print(f"Next steps: {', '.join(meta['next_steps'])}")

    errors = meta.get("errors", {})
    if errors:
        print(f"\nErrors: {dict(errors)}")

if __name__ == "__main__":
    asyncio.run(main())
