"""Example 1: Basic parallel research — 3 agents, DAG execution.

Run: python examples/01_basic.py
"""
import asyncio
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_swarm import Swarm, SubTask

# Replace with your LLM (OpenAI, Claude, etc.)
async def mock_llm(prompt, tools=None):
    """Smart mock that responds based on role."""
    if "Researcher" in prompt:
        return "Found 3 key competitors: AlphaAI (leader, $50M ARR), BetaML (fast-growing, $12M), GammaLabs (niche, $3M)."
    elif "Analyst" in prompt:
        return "AlphaAI leads in enterprise but weak in developer experience. BetaML growing 200% YoY. GammaLabs has best accuracy in medical domain."
    elif "Writer" in prompt:
        return "Executive Summary: The AI market has 3 main players. AlphaAI dominates enterprise, BetaML is the fastest grower, and GammaLabs owns the medical niche. Recommendation: target the developer segment where AlphaAI is weakest."
    return f"Processed: {prompt[:50]}..."

async def main():
    swarm = Swarm(llm=mock_llm)
    result = await swarm.run(
        goal="Analyze the AI agent market",
        tasks=[
            SubTask(id="research", description="Find top competitors in AI agent space", role="Researcher"),
            SubTask(id="analyze", description="Compare strengths and weaknesses", role="Analyst", dependencies=["research"]),
            SubTask(id="report", description="Write executive summary with recommendation", role="Writer", dependencies=["analyze"]),
        ]
    )

    print("=== Output ===")
    print(result["final_output"])
    print(f"\n=== Stats ===")
    meta = result["metadata"]
    print(f"Tasks: {meta['succeeded']}/{meta['total_tasks']} succeeded")
    print(f"Time: {meta['execution_time_s']}s")
    print(f"Waves: {meta['waves']}")
    if meta.get("next_steps"):
        print(f"Suggested next: {', '.join(meta['next_steps'])}")

if __name__ == "__main__":
    asyncio.run(main())
