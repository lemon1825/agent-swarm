"""Scenario: Competitor Analysis Pipeline

5 agents work in parallel to research, analyze, compare, recommend, and review.
Budget cap prevents runaway LLM costs. Ontology ensures role-task compatibility.

Usage:
    # With mock LLM (no API key needed)
    python examples/04_competitor_analysis.py

    # With real OpenAI
    export OPENAI_API_KEY=sk-xxx
    python examples/04_competitor_analysis.py --real
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_swarm import (
    Swarm, SubTask, SkillBank, SkillGenetics, Skill,
    BudgetPolicy, OntologyRegistry, OntologyGateMode, CORE_ONTOLOGY,
    SkillManifest,
)


# ── Mock LLM (works without API key) ──────────────────────

MOCK_RESPONSES = {
    "market": "Top 5 competitors: LangGraph (most stars), CrewAI (fastest growth), AutoGen (Microsoft backing), Semantic Kernel (enterprise), Haystack (RAG focus).",
    "features": "LangGraph: state graphs, persistence. CrewAI: role-based crews, visual builder. AutoGen: multi-turn conversation. Semantic Kernel: .NET/Python, planners. Haystack: pipeline-first, modular.",
    "pricing": "LangGraph: free core, LangSmith $39/seat. CrewAI: free core, $99-$120k/yr hosted. AutoGen: free (Microsoft). Semantic Kernel: free. Haystack: free core, deepset Cloud paid.",
    "compare": "Agent Swarm differentiator: zero deps, skill evolution, ontology routing. Weakness: no UI, no hosted version. Opportunity: embedded engine market underserved.",
    "recommend": "Recommendation: Position as 'the engine you embed' vs 'the platform you deploy'. Target: product teams building internal tools. Pricing: $49/mo Pro, $249/mo Team.",
    "review": "Review: Analysis is solid. Missing: user testimonials, benchmark data. Approved with minor edits.",
}

async def mock_llm(prompt, tools=None):
    p = prompt.lower()
    for key, response in MOCK_RESPONSES.items():
        if key in p:
            return response
    return "Analysis complete. Key findings documented."


# ── Real LLM (optional) ──────────────────────────────────

async def real_llm(prompt, tools=None):
    from openai import AsyncOpenAI
    client = AsyncOpenAI()
    r = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
    )
    return r.choices[0].message.content


# ── Pipeline ──────────────────────────────────────────────

async def main():
    use_real = "--real" in sys.argv
    llm = real_llm if use_real else mock_llm

    print("=" * 60)
    print("  Competitor Analysis Pipeline")
    print(f"  LLM: {'GPT-4o-mini' if use_real else 'Mock'}")
    print("=" * 60)

    # Setup: skills, genetics, ontology, budget
    bank = SkillBank()
    bank.add(Skill(name="MarketResearch", principle="Find current market data with source verification",
                   when_to_apply="research, market, competitor",
                   manifest=SkillManifest(capabilities=["sw:SkillCap/WebSearch"],
                                          task_types=["sw:TaskType/Research"])))
    bank.add(Skill(name="StrategyAnalysis", principle="Compare positioning using SWOT framework",
                   when_to_apply="analysis, strategy, comparison",
                   manifest=SkillManifest(capabilities=["sw:SkillCap/DataAnalysis"],
                                          task_types=["sw:TaskType/Analysis"])))

    genetics = SkillGenetics(bank)
    for s in bank._all():
        genetics.register_lineage(s)

    swarm = Swarm(
        llm=llm,
        skill_bank=bank,
        genetics=genetics,
        ontology=OntologyRegistry([CORE_ONTOLOGY]),
        ontology_gate_mode=OntologyGateMode.WARN,
        budget_policy=BudgetPolicy(max_cost_per_run=1.00),
    )

    # Define the 5-agent pipeline
    result = await swarm.run(
        "Analyze the AI agent framework market and recommend positioning strategy",
        tasks=[
            # Wave 1: 3 researchers run in parallel
            SubTask(id="market", description="Research top 5 AI agent frameworks by adoption and stars",
                    role="Researcher"),
            SubTask(id="features", description="Research feature comparison across frameworks",
                    role="Researcher"),
            SubTask(id="pricing", description="Research pricing models of each framework",
                    role="Researcher"),
            # Wave 2: analyst compares (depends on all 3 researchers)
            SubTask(id="compare", description="Compare Agent Swarm positioning vs competitors using SWOT",
                    role="Analyst", dependencies=["market", "features", "pricing"]),
            # Wave 3: writer recommends (depends on analysis)
            SubTask(id="recommend", description="Write positioning recommendation with pricing strategy",
                    role="Writer", dependencies=["compare"]),
        ]
    )

    # Output
    meta = result["metadata"]
    print(f"\n{'=' * 60}")
    print(f"  Results")
    print(f"{'=' * 60}")
    print(f"  Tasks: {meta['succeeded']}/{meta['total_tasks']} succeeded")
    print(f"  Time: {meta['execution_time_s']:.2f}s")
    print(f"  Budget: ${meta.get('budget_spent_usd', 0):.4f}")
    print(f"  Waves: 3 (parallel research → analysis → recommendation)")

    if "genetics" in meta:
        eff = meta["genetics"].get("effectiveness", {})
        print(f"  Genetics: {eff.get('verdict', 'n/a')}")

    print(f"\n  Final output:")
    print(f"  {result['final_output'][:200]}...")

    # Show each task result
    print(f"\n  Task details:")
    for tid, tr in result["results"].items():
        status = "✓" if tr.success else "✗"
        print(f"    {status} [{tid}] {tr.role}: {str(tr.output)[:80]}...")


if __name__ == "__main__":
    asyncio.run(main())
