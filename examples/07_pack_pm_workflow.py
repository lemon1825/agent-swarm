"""Scenario: PM Discovery-to-Launch with Skill Pack

Uses the pm-pack to run a full product workflow:
discovery → positioning → PRD → launch planning.

Demonstrates:
- Installing and using a skill pack
- Pack skills injected into agents
- Pack ontology terms enabling smarter routing
- Combined playbook + pack execution

Usage:
    python examples/07_pack_pm_workflow.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_swarm import (
    Swarm, SubTask, SkillBank, SkillGenetics,
    OntologyRegistry, OntologyGateMode, CORE_ONTOLOGY,
    PackManager,
)


async def mock_llm(prompt, tools=None):
    p = prompt.lower()
    if "discover" in p or "opportunity" in p:
        return "Market opportunity: AI agent orchestration for internal tools. TAM: $2.3B by 2027. Gap: no lightweight embedded solution exists."
    if "position" in p or "value prop" in p:
        return "Position: 'The agent engine you embed.' Target: product teams building internal AI tools. Differentiator: zero deps, skill evolution, ontology routing."
    if "prd" in p or "requirement" in p:
        return "PRD: Agent Swarm Pro. Problem: teams need dashboards for agent workflows. Goals: run visibility, approval UI, cost tracking. Non-goals: replacing LangGraph."
    if "launch" in p or "go-to-market" in p:
        return "Launch plan: Week 1 GitHub + PyPI. Week 2 Show HN + dev.to blog. Week 3 Reddit. Week 4 Pro waitlist. Success: 500 stars, 10 Pro signups."
    return "Task completed."


async def main():
    print("=" * 60)
    print("  PM Discovery-to-Launch with pm-pack")
    print("=" * 60)

    # 1. Install pack
    pm = PackManager()
    pm.install("pm-pack")
    print(f"\n  Installed pm-pack: {len(pm.get('pm-pack').skills)} skills")

    # 2. Apply pack to SkillBank + Ontology
    bank, bundles = pm.apply()
    genetics = SkillGenetics(bank)
    for s in bank._all():
        genetics.register_lineage(s)

    ontology = OntologyRegistry([CORE_ONTOLOGY] + bundles)
    print(f"  Combined ontology: {ontology.get_stats()['terms']} terms")
    print(f"  Skills loaded: {len(bank._all())}")

    # 3. Run PM workflow
    swarm = Swarm(
        llm=mock_llm,
        skill_bank=bank,
        genetics=genetics,
        ontology=ontology,
        ontology_gate_mode=OntologyGateMode.WARN,
    )

    result = await swarm.run(
        "Define and launch an AI agent dashboard product",
        tasks=[
            SubTask(id="discover", description="Discover market opportunity for AI agent dashboards",
                    role="Researcher"),
            SubTask(id="position", description="Define value proposition and competitive positioning",
                    role="Analyst", dependencies=["discover"]),
            SubTask(id="prd", description="Write PRD with requirements and success metrics",
                    role="Writer", dependencies=["position"]),
            SubTask(id="launch", description="Create go-to-market launch plan",
                    role="Writer", dependencies=["prd"]),
        ]
    )

    # 4. Output
    meta = result["metadata"]
    print(f"\n{'=' * 60}")
    print(f"  Results")
    print(f"{'=' * 60}")
    print(f"  Tasks: {meta['succeeded']}/{meta['total_tasks']} succeeded")
    print(f"  Time: {meta['execution_time_s']:.2f}s")

    if "genetics" in meta:
        print(f"  Genetics: {meta['genetics'].get('effectiveness', {}).get('verdict', 'n/a')}")

    print(f"\n  Workflow:")
    for tid, tr in result["results"].items():
        status = "✓" if tr.success else "✗"
        print(f"    {status} [{tid}] {tr.role}")
        print(f"      → {str(tr.output)[:100]}...")

    print(f"\n  Pack skills used: pm-pack ({len(pm.get('pm-pack').skills)} skills)")
    print(f"  Next steps: {meta.get('next_steps', [])}")


if __name__ == "__main__":
    asyncio.run(main())
