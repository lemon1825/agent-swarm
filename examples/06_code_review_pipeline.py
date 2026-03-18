"""Scenario: Code Review Pipeline

4-step code review: scan → prioritize → fix suggestions → lead approval.
Uses the built-in code_review playbook and ontology-guided role routing.

This demonstrates:
- Built-in playbook (code_review)
- Ontology-driven role assignment
- Schema validation on output
- Skill genetics improving review quality over time

Usage:
    python examples/06_code_review_pipeline.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent_swarm import (
    Swarm, SubTask, SkillBank, SkillGenetics, Skill,
    OntologyRegistry, OntologyGateMode, CORE_ONTOLOGY,
    SkillManifest, SCHEMA_PRESETS, MultiValidator,
)


# ── Mock LLM ──────────────────────────────────────────────

MOCK_RESPONSES = {
    "scan": """{
        "findings": [
            {"file": "auth.py", "line": 42, "severity": "HIGH", "type": "SQL Injection", "description": "User input passed directly to query without parameterization"},
            {"file": "api.py", "line": 118, "severity": "MEDIUM", "type": "Missing Auth", "description": "Endpoint /admin/users lacks authentication middleware"},
            {"file": "utils.py", "line": 7, "severity": "LOW", "type": "Unused Import", "description": "os module imported but never used"},
            {"file": "config.py", "line": 23, "severity": "HIGH", "type": "Hardcoded Secret", "description": "Database password hardcoded in source"}
        ],
        "summary": "4 findings: 2 HIGH, 1 MEDIUM, 1 LOW"
    }""",
    "prioritize": """{
        "priority_order": [
            {"rank": 1, "file": "auth.py:42", "reason": "SQL injection is exploitable in production", "effort": "30 min"},
            {"rank": 2, "file": "config.py:23", "reason": "Hardcoded secrets can be extracted from repo history", "effort": "15 min"},
            {"rank": 3, "file": "api.py:118", "reason": "Admin endpoint exposed without auth", "effort": "20 min"},
            {"rank": 4, "file": "utils.py:7", "reason": "Code cleanliness, no security impact", "effort": "2 min"}
        ],
        "total_effort": "~67 min",
        "recommendation": "Fix HIGH items before next deploy"
    }""",
    "fix": """{
        "fixes": [
            {"file": "auth.py:42", "before": "cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')", "after": "cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))", "explanation": "Use parameterized query to prevent SQL injection"},
            {"file": "config.py:23", "before": "DB_PASSWORD = 'yw02280228'", "after": "DB_PASSWORD = os.environ.get('DB_PASSWORD')", "explanation": "Move secrets to environment variables"},
            {"file": "api.py:118", "before": "@app.get('/admin/users')", "after": "@app.get('/admin/users', dependencies=[Depends(require_admin)])", "explanation": "Add authentication dependency"}
        ],
        "summary": "3 fixes provided for HIGH and MEDIUM issues"
    }""",
    "approve": "Review approved. All HIGH severity fixes are correct. config.py fix needs .env file setup documentation. Ship after adding that note.",
}

async def mock_llm(prompt, tools=None):
    p = prompt.lower()
    for key, response in MOCK_RESPONSES.items():
        if key in p:
            return response
    return '{"status": "complete"}'


# ── Approval ──────────────────────────────────────────────

async def lead_approval(task_id, description, role):
    print(f"\n  🔔 LEAD APPROVAL: {description}")
    print(f"     ✅ Auto-approved (demo mode)")
    return True


# ── Pipeline ──────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("  Code Review Pipeline")
    print("=" * 60)

    # Skills for code review
    bank = SkillBank()
    bank.add(Skill(name="SecurityScan", principle="Check for OWASP Top 10 vulnerabilities",
                   when_to_apply="security, scan, vulnerability, injection",
                   manifest=SkillManifest(capabilities=["sw:SkillCap/CodeAnalysis"],
                                          task_types=["sw:TaskType/Review"])))
    bank.add(Skill(name="CodeFix", principle="Provide minimal, targeted fixes with before/after",
                   when_to_apply="fix, patch, refactor, suggestion",
                   manifest=SkillManifest(capabilities=["sw:SkillCap/TextGeneration"],
                                          task_types=["sw:TaskType/Writing"])))

    genetics = SkillGenetics(bank)
    for s in bank._all():
        genetics.register_lineage(s)

    swarm = Swarm(
        llm=mock_llm,
        skill_bank=bank,
        genetics=genetics,
        ontology=OntologyRegistry([CORE_ONTOLOGY]),
        ontology_gate_mode=OntologyGateMode.WARN,
        approval_callback=lead_approval,
    )

    # Run with built-in code_review playbook
    result = await swarm.run(
        "Review the authentication module for security vulnerabilities",
        playbook="code_review",
    )

    # Also run with manual tasks for more control
    result2 = await swarm.run(
        "Full security review of the codebase",
        tasks=[
            SubTask(id="scan", description="Scan codebase for security vulnerabilities",
                    role="Reviewer"),
            SubTask(id="prioritize", description="Prioritize findings by severity and exploitability",
                    role="Analyst", dependencies=["scan"]),
            SubTask(id="fix", description="Write fix suggestions with before/after code",
                    role="Writer", dependencies=["prioritize"]),
            SubTask(id="approve", description="Review fixes and approve for deployment",
                    role="Reviewer", dependencies=["fix"]),
        ]
    )

    # Output
    meta = result2["metadata"]
    print(f"\n{'=' * 60}")
    print(f"  Pipeline Results")
    print(f"{'=' * 60}")
    print(f"  Tasks: {meta['succeeded']}/{meta['total_tasks']} succeeded")
    print(f"  Time: {meta['execution_time_s']:.2f}s")

    if "genetics" in meta:
        print(f"  Genetics: {meta['genetics'].get('effectiveness', {}).get('verdict', 'n/a')}")

    # Show findings
    print(f"\n  Step results:")
    for tid, tr in result2["results"].items():
        status = "✓" if tr.success else "✗"
        output = str(tr.output)
        # Show first 120 chars
        print(f"    {status} [{tid}] {tr.role}")
        print(f"      {output[:120]}...")

    # Show playbook result for comparison
    meta1 = result["metadata"]
    print(f"\n  Playbook mode (code_review):")
    print(f"    Tasks: {meta1['succeeded']}/{meta1['total_tasks']}")
    print(f"    Next steps: {meta1.get('next_steps', [])}")


if __name__ == "__main__":
    asyncio.run(main())
