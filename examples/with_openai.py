"""Example: Connect to OpenAI GPT-4.

Setup:
    pip install openai
    export OPENAI_API_KEY=sk-...

Run:
    python examples/with_openai.py
"""
import asyncio
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_swarm import Swarm, SubTask, BudgetPolicy

async def openai_llm(prompt: str, tools=None) -> str:
    """Call OpenAI API. Agent Swarm handles timeout, retry, rate limit automatically."""
    try:
        from openai import AsyncOpenAI
    except ImportError:
        print("Install openai: pip install openai")
        raise

    client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
        temperature=0.7,
    )
    return response.choices[0].message.content

async def main():
    if not os.environ.get("OPENAI_API_KEY"):
        print("Set OPENAI_API_KEY environment variable first.")
        print("  export OPENAI_API_KEY=sk-...")
        return

    swarm = Swarm(
        llm=openai_llm,
        budget_policy=BudgetPolicy(max_cost_per_run=0.50, block_on_exceed=True),
    )

    result = await swarm.run(
        goal="Analyze the current state of AI agent frameworks",
        tasks=[
            SubTask(id="research", description="List top 5 AI agent frameworks in 2025 with pros/cons", role="Researcher"),
            SubTask(id="compare", description="Create a comparison table of the frameworks", role="Analyst", dependencies=["research"]),
            SubTask(id="recommend", description="Write a recommendation for a startup choosing a framework", role="Writer", dependencies=["compare"]),
        ]
    )

    print("=== Output ===")
    print(result["final_output"])
    meta = result["metadata"]
    print(f"\n--- {meta['succeeded']}/{meta['total_tasks']} tasks, {meta['execution_time_s']}s, ${meta['budget_spent_usd']:.4f} ---")
    if meta.get("next_steps"):
        print(f"Next: {', '.join(meta['next_steps'])}")

    # Check for errors
    errors = meta.get("errors", {})
    if errors:
        print(f"\nErrors encountered: {dict(errors)}")
        print("(Agent Swarm handled these automatically via retry/backoff)")

if __name__ == "__main__":
    asyncio.run(main())
