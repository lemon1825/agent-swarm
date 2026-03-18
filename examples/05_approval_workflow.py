"""Scenario: Content Pipeline with Approval Gates

4-step content production: research → write → review (approval) → publish (approval).
The reviewer and publisher must approve before the pipeline continues.

This demonstrates:
- Human approval gates (approval_callback)
- Sequential dependencies with approval checkpoints
- Org chart handoff validation
- Budget tracking across the pipeline

Usage:
    python examples/05_approval_workflow.py
    python examples/05_approval_workflow.py --reject   # See what happens when reviewer rejects
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_swarm import (
    Swarm, SubTask, BudgetPolicy, OrgNode,
)


# ── Mock LLM ──────────────────────────────────────────────

async def mock_llm(prompt, tools=None):
    p = prompt.lower()
    if "research" in p or "source" in p:
        return "Sources found: McKinsey AI report 2025, Gartner agent forecast, YC batch analysis. Key finding: 73% of enterprises plan to adopt agent frameworks by 2026."
    if "draft" in p or "write" in p:
        return "Draft: 'The AI Agent Revolution: Why 2026 Is the Year of Orchestration'. Opening paragraph discusses the shift from single-model apps to multi-agent systems. Includes 3 case studies and market sizing."
    if "review" in p or "check" in p:
        return "Review notes: Strong opening, data is current. Suggestion: add comparison table. Minor grammar fixes needed in paragraph 3. Overall: ready for publication with edits."
    if "publish" in p or "final" in p:
        return "Published: Blog post live at /blog/ai-agent-revolution. Social media scheduled: LinkedIn (9am), Twitter/X (10am), dev.to cross-post (11am). Newsletter blast queued for 2pm."
    return "Task completed successfully."


# ── Approval Callbacks ────────────────────────────────────

class ApprovalSimulator:
    """Simulates human approval. In production, this would be Slack/email/web UI."""

    def __init__(self, reject_review: bool = False):
        self.reject_review = reject_review
        self.log = []

    async def callback(self, task_id: str, description: str, role: str) -> bool:
        """Called by the engine when a task needs approval."""
        print(f"\n  🔔 APPROVAL REQUEST")
        print(f"     Task: {task_id}")
        print(f"     Description: {description}")
        print(f"     Role: {role}")

        # Simulate decision
        if task_id == "review" and self.reject_review:
            print(f"     Decision: ❌ REJECTED")
            self.log.append({"task": task_id, "approved": False})
            return False

        print(f"     Decision: ✅ APPROVED")
        self.log.append({"task": task_id, "approved": True})
        return True


# ── Pipeline ──────────────────────────────────────────────

async def main():
    reject_mode = "--reject" in sys.argv
    approver = ApprovalSimulator(reject_review=reject_mode)

    print("=" * 60)
    print("  Content Pipeline with Approval Gates")
    print(f"  Mode: {'REJECT at review' if reject_mode else 'APPROVE all'}")
    print("=" * 60)

    swarm = Swarm(
        llm=mock_llm,
        approval_callback=approver.callback,
        budget_policy=BudgetPolicy(max_cost_per_run=0.50),
    )

    result = await swarm.run(
        "Produce blog post about AI agent trends for company blog",
        tasks=[
            # Step 1: Research (no approval needed)
            SubTask(id="research",
                    description="Find 3 authoritative sources on AI agent adoption trends",
                    role="Researcher"),

            # Step 2: Write draft (no approval needed)
            SubTask(id="draft",
                    description="Write 800-word blog post with case studies and data",
                    role="Writer",
                    dependencies=["research"]),

            # Step 3: Editorial review (APPROVAL REQUIRED)
            SubTask(id="review",
                    description="Review draft for accuracy, tone, and brand alignment",
                    role="Reviewer",
                    dependencies=["draft"]),

            # Step 4: Publish (APPROVAL REQUIRED)
            SubTask(id="publish",
                    description="Finalize, schedule social media, queue newsletter",
                    role="Publisher",
                    dependencies=["review"]),
        ]
    )

    # Output
    meta = result["metadata"]
    print(f"\n{'=' * 60}")
    print(f"  Pipeline Results")
    print(f"{'=' * 60}")
    print(f"  Tasks succeeded: {meta['succeeded']}/{meta['total_tasks']}")
    print(f"  Tasks failed: {meta['failed']}/{meta['total_tasks']}")
    print(f"  Time: {meta['execution_time_s']:.2f}s")

    # Show each step
    print(f"\n  Step-by-step:")
    for tid, tr in result["results"].items():
        status = "✓" if tr.success else "✗"
        approval_note = ""
        # Check if this task had approval
        for entry in approver.log:
            if entry["task"] == tid:
                approval_note = " [APPROVED ✅]" if entry["approved"] else " [REJECTED ❌]"
        print(f"    {status} {tid} ({tr.role}){approval_note}")
        if tr.success:
            print(f"      → {str(tr.output)[:100]}...")
        else:
            print(f"      → BLOCKED (dependency failed or rejected)")

    # Approval audit trail
    print(f"\n  Approval audit trail:")
    for entry in approver.log:
        icon = "✅" if entry["approved"] else "❌"
        print(f"    {icon} {entry['task']}")

    if reject_mode:
        print(f"\n  Note: 'review' was rejected, so 'publish' was never executed.")
        print(f"  This is the expected behavior — rejected work stops cleanly.")


if __name__ == "__main__":
    asyncio.run(main())
