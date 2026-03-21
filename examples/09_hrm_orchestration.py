"""HRM 2-Tier Orchestration — H-module plans, L-module executes to convergence.

Demonstrates the Hierarchical Reasoning Model pattern:
- H-module (slow): strategic planning, re-plans based on feedback
- L-module (fast): rapid execution with convergence detection
- ACT: automatic halt when quality target met
"""
import asyncio
from agent_swarm import HRMOrchestrator, HRMConfig
from agent_swarm.convergence import ConvergenceConfig


async def h_planner(goal, feedback, prev_score):
    """Strategic planner — adjusts approach based on feedback."""
    if feedback and prev_score < 0.7:
        return {"strategy": "deep_dive", "focus": feedback[:50]}
    return {"strategy": "broad_scan", "focus": goal}


async def l_executor(plan, feedback):
    """Rapid executor — produces artifacts based on plan."""
    strategy = plan.get("strategy", "default")
    depth = 5 if strategy == "deep_dive" else 3
    return {"analysis": f"Result with depth={depth}", "confidence": 0.6 + depth * 0.05}


async def evaluator(artifact):
    """Evaluates output quality."""
    confidence = artifact.get("confidence", 0.5)
    score = min(1.0, confidence + 0.1)
    feedback = "needs more depth" if score < 0.8 else "good quality"
    return score, feedback


async def main():
    orchestrator = HRMOrchestrator(HRMConfig(
        h_max_cycles=3,
        quality_target=0.85,
        l_convergence=ConvergenceConfig(max_iterations=3, min_iterations=1),
    ))

    result = await orchestrator.run(
        goal="Analyze AI agent market trends",
        h_planner=h_planner,
        l_executor=l_executor,
        evaluator=evaluator,
    )

    print(f"Success: {result.success}")
    print(f"Final score: {result.final_score:.2f}")
    print(f"H-cycles: {result.h_cycles}, L-iterations: {result.total_l_iterations}")
    print(f"Reason: {result.reason}")
    for i, cycle in enumerate(result.cycles):
        print(f"  Cycle {i}: score={cycle.evaluation_score:.2f} "
              f"strategy={cycle.h_state.plan.get('strategy')} "
              f"revised={cycle.h_state.revised}")


if __name__ == "__main__":
    asyncio.run(main())
