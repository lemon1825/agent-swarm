"""Example 3: Production setup — strict ontology, approval gate, budget, schema validation.

Run: python examples/03_production.py
"""
import asyncio
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_swarm import (
    Swarm, SubTask, OntologyRegistry, OntologyGateMode, CORE_ONTOLOGY,
    SkillBank, Skill, SkillManifest, BudgetPolicy, GoalAncestry,
    MultiValidator, SCHEMA_PRESETS, MetricsCollector,
)

async def mock_llm(prompt, tools=None):
    if "Researcher" in prompt:
        return '{"title":"AI Market Research Q1","sources":["Gartner 2025","McKinsey AI Report"],"findings":"The AI agent market is projected to reach $50B by 2027. Key growth drivers include enterprise automation and developer tooling.","confidence":0.85}'
    elif "Analyst" in prompt:
        return "Analysis: Enterprise segment growing 40% YoY. Developer tools segment underserved but high demand. Recommendation: focus on developer-first approach."
    elif "Writer" in prompt:
        return "Final Report: AI agent market shows strong growth potential. The developer tools segment represents an underserved $8B opportunity."
    return f"Processed: {prompt[:50]}..."

async def auto_approve(task_id, description, role):
    """Simulated approval — in production, this would be a UI callback."""
    print(f"  📋 Auto-approving: [{role}] {description[:50]}...")
    return True

async def main():
    registry = OntologyRegistry([CORE_ONTOLOGY])
    metrics = MetricsCollector()

    # Skill bank with ontology-aware capabilities
    bank = SkillBank()
    bank.add(Skill(name="WebSearch", principle="Search and find sources",
                   when_to_apply="research, investigation",
                   manifest=SkillManifest(
                       capabilities=["sw:SkillCap/WebSearch"],
                       task_types=["sw:TaskType/Research"],
                       artifact_types=["sw:ArtifactType/Summary"],
                   )))
    bank.add(Skill(name="DataAnalysis", principle="Analyze data patterns",
                   when_to_apply="analysis, comparison",
                   manifest=SkillManifest(
                       capabilities=["sw:SkillCap/DataAnalysis"],
                       task_types=["sw:TaskType/Analysis"],
                   )))
    bank.add(Skill(name="TextGen", principle="Generate written content",
                   when_to_apply="writing, report, summary",
                   manifest=SkillManifest(
                       capabilities=["sw:SkillCap/TextGeneration"],
                       task_types=["sw:TaskType/Writing"],
                       artifact_types=["sw:ArtifactType/Report"],
                   )))

    swarm = Swarm(
        llm=mock_llm,
        ontology=registry,
        ontology_gate_mode=OntologyGateMode.STRICT,  # Block on ontology violations
        skill_bank=bank,
        approval_callback=auto_approve,
        budget_policy=BudgetPolicy(max_cost_per_run=1.00, block_on_exceed=True),
        goal_ancestry=GoalAncestry(mission="Become #1 AI agent platform", objective="Validate market opportunity"),
        validator=MultiValidator([SCHEMA_PRESETS["research_report"]]),
        metrics=metrics,
    )

    print("=== Running with STRICT ontology + approval + budget ===\n")

    result = await swarm.run(
        goal="Research AI agent market opportunity",
        tasks=[
            SubTask(id="research", description="Gather market data", role="Researcher"),
            SubTask(id="analyze", description="Analyze market segments", role="Analyst", dependencies=["research"]),
            SubTask(id="report", description="Write investment memo", role="Writer", dependencies=["analyze"], requires_approval=True),
        ]
    )

    print(f"\n=== Results ===")
    meta = result["metadata"]
    print(f"Success: {meta['succeeded']}/{meta['total_tasks']}")
    print(f"Budget: ${meta['budget_spent_usd']:.4f}")
    print(f"Time: {meta['execution_time_s']}s")

    # Show tickets
    print(f"\n=== Tickets ===")
    for t in meta["tickets"]:
        print(f"  [{t['priority']}] {t['ticket_id']} — {t['status']} (${t['actual_cost']:.4f})")
        if t["goal_chain"]: print(f"    Goal chain: {t['goal_chain']}")

    # Show next steps from ontology
    if meta.get("next_steps"):
        print(f"\n=== Ontology Next Steps ===")
        print(f"  {', '.join(meta['next_steps'])}")

    # Show metrics
    print(f"\n=== Metrics ===")
    m = metrics.to_dict()
    dur = m["task_duration_ms"]
    print(f"  Task latency: p50={dur['p50']}ms, p95={dur['p95']}ms")
    print(f"  Success rate: {m['success_rate']}")

    # Show plan validation
    pq = meta.get("plan_quality", {})
    if pq.get("ontology_warnings"):
        print(f"\n=== Ontology Warnings ===")
        for w in pq["ontology_warnings"]: print(f"  ⚠ {w}")
    else:
        print(f"\n  ✓ Plan passed ontology validation")

if __name__ == "__main__":
    asyncio.run(main())
