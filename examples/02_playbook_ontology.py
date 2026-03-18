"""Example 2: Product discovery with playbook + ontology-driven recommendations.

Run: python examples/02_playbook_ontology.py
"""
import asyncio
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_swarm import (
    Swarm, OntologyRegistry, OntologyGateMode, CORE_ONTOLOGY,
    OntologyBundle, OntologyTerm, OntologyRelation,
    SkillBank, Skill, SkillManifest,
)

async def mock_llm(prompt, tools=None):
    if "Ideation" in prompt or "Ideator" in prompt:
        return "Ideas: 1) AI-powered code review bot 2) Natural language database queries 3) Automated API documentation"
    elif "Assumption" in prompt or "Risk" in prompt:
        return "Key assumptions: Value: developers want AI reviews. Usability: <5min setup. Viability: $20/mo pricing. Feasibility: GPT-4 quality sufficient."
    elif "Prioritiz" in prompt:
        return "Priority: 1. Value assumption (highest risk) 2. Feasibility (medium) 3. Usability (low) 4. Viability (low)"
    elif "Experiment" in prompt:
        return "Experiment: Landing page test with 'Sign up for AI code review' CTA. Metric: >5% conversion in 2 weeks."
    return f"Processed: {prompt[:50]}..."

async def main():
    # Extend core ontology with our domain
    dev_tools = OntologyBundle(
        bundle_id="dev-tools", version="0.1.0",
        terms=[
            OntologyTerm(id="sw:TaskType/CodeReview", label="Code Review",
                         parents=["sw:TaskType/Review"], aliases=["코드리뷰"]),
            OntologyTerm(id="sw:SkillCap/StaticAnalysis", label="Static Analysis"),
        ],
        relations=[
            OntologyRelation("sw:requires", "sw:TaskType/CodeReview", "sw:SkillCap/StaticAnalysis"),
            OntologyRelation("sw:requires", "sw:TaskType/CodeReview", "sw:SkillCap/CodeAnalysis"),
        ]
    )

    registry = OntologyRegistry([CORE_ONTOLOGY, dev_tools])

    # Create skill bank with ontology-aware skills
    bank = SkillBank()
    bank.add(Skill(
        name="Web Research",
        principle="Search and synthesize information from multiple sources",
        when_to_apply="research, discovery, market analysis",
        manifest=SkillManifest(
            capabilities=["sw:SkillCap/WebSearch"],
            task_types=["sw:TaskType/Research"],
            domain="research",
        )
    ))

    swarm = Swarm(
        llm=mock_llm,
        ontology=registry,
        ontology_gate_mode=OntologyGateMode.WARN,  # Log warnings, don't block
        skill_bank=bank,
    )

    # Run product discovery playbook
    result = await swarm.run(
        goal="Explore AI-powered developer tools as a new product direction",
        playbook="discover",
    )

    print("=== Product Discovery Results ===")
    for tid, r in result["results"].items():
        status = "✓" if r.success else "✗"
        print(f"  {status} [{r.role}] {r.output[:80]}...")

    print(f"\n=== Recommendations ===")
    next_steps = result["metadata"].get("next_steps", [])
    print(f"Next steps: {', '.join(next_steps)}")

    print(f"\n=== Ontology Insights ===")
    plan_quality = result["metadata"].get("plan_quality", {})
    if plan_quality.get("ontology_warnings"):
        for w in plan_quality["ontology_warnings"]:
            print(f"  ⚠ {w}")
    else:
        print("  All tasks aligned with ontology.")

    print(f"\n=== Extended Ontology ===")
    stats = registry.get_stats()
    print(f"  Terms: {stats['terms']}, Relations: {stats['relations']}")
    print(f"  Code Review requires: {registry.task_requires('sw:TaskType/CodeReview')}")

if __name__ == "__main__":
    asyncio.run(main())
