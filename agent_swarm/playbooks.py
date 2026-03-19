"""SOP Playbooks — 7 built-in workflow templates."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from typing import Any, Optional

@dataclass
class SOPStep:
    name: str; role: str; description: str; instructions: str = ""
    expected_output: str = ""; depends_on: List[str] = field(default_factory=list)
    output_must_contain: List[str] = field(default_factory=list)
    requires_approval: bool = False
    gate: Optional[Dict[str, Any]] = None
    # gate format: {"type": "approval|keyword|custom", "condition": "...", "block_message": "..."}

@dataclass
class SOPPlaybook:
    name: str; description: str; steps: List[SOPStep] = field(default_factory=list)
    context_template: str = ""; next_steps: List[str] = field(default_factory=list)
    def to_tasks(self, goal="", context=""):
        from .core import SubTask
        tasks = []; step_map = {}
        for i, step in enumerate(self.steps):
            tid = f"sop_{i}_{step.name.lower().replace(' ', '_')}"
            t = SubTask(id=tid, description=f"[SOP:{self.name}] {step.description}" + (f"\nGoal:{goal}" if goal else ""),
                role=step.role, instructions=step.instructions, expected_output=step.expected_output,
                dependencies=[f"sop_{j}_{self.steps[j].name.lower().replace(' ', '_')}" for j in range(len(self.steps)) if self.steps[j].name in step.depends_on],
                requires_approval=step.requires_approval)
            if step.gate:
                t.metadata = {"gate": step.gate}
            tasks.append(t)
            step_map[tid] = step
        return tasks, step_map

PLAYBOOK_RESEARCH = SOPPlaybook(name="Research Report", description="research→analyze→verify→write",
    steps=[SOPStep(name="Research", role="Researcher", description="Gather data", instructions="Find 3+ sources.", expected_output="Findings"),
           SOPStep(name="Analysis", role="Analyst", description="Analyze findings", instructions="Identify patterns.", expected_output="Insights", depends_on=["Research"]),
           SOPStep(name="Verification", role="Fact Checker", description="Cross-verify", instructions="Check claims.", expected_output="Verification report", depends_on=["Analysis"]),
           SOPStep(name="Writing", role="Writer", description="Final report", instructions="Intro→Findings→Conclusion.", expected_output="Report", depends_on=["Verification"])],
    context_template="Follow SOP: research→analyze→verify→write.", next_steps=["strategy", "write_prd"])

PLAYBOOK_CODE_REVIEW = SOPPlaybook(name="Code Review", description="analysis→security→report",
    steps=[SOPStep(name="Static Analysis", role="Code Analyst", description="Code structure", instructions="Check complexity.", expected_output="Issue list"),
           SOPStep(name="Security Audit", role="Security Reviewer", description="Vulnerabilities", instructions="Check injection/auth.", expected_output="Findings", depends_on=["Static Analysis"]),
           SOPStep(name="Quality Report", role="Quality Lead", description="Synthesize", instructions="Prioritize.", expected_output="Report", depends_on=["Static Analysis", "Security Audit"])],
    next_steps=["plan_launch"])

PLAYBOOK_DISCOVER = SOPPlaybook(name="Product Discovery", description="ideate→assumptions→prioritize→experiment",
    steps=[SOPStep(name="Ideation", role="PM Ideator", description="Brainstorm ideas from PM, Designer, Engineer perspectives", instructions="Generate 10+ ideas.", expected_output="Idea list with rationale"),
           SOPStep(name="Assumptions", role="Risk Analyst", description="Identify risky assumptions across Value, Usability, Viability, Feasibility", instructions="Map each idea to assumptions.", expected_output="Assumption map", depends_on=["Ideation"]),
           SOPStep(name="Prioritization", role="Strategist", description="Prioritize assumptions by risk and impact", instructions="Use ICE or RICE. Rank top 5.", expected_output="Prioritized list", depends_on=["Assumptions"]),
           SOPStep(name="Experiment Design", role="Experiment Designer", description="Design lean experiments for top assumptions", instructions="Hypothesis, method, metric, timeline.", expected_output="Experiment plan", depends_on=["Prioritization"])],
    context_template="Run full product discovery cycle.", next_steps=["strategy", "write_prd"])

PLAYBOOK_STRATEGY = SOPPlaybook(name="Product Strategy", description="vision→positioning→competitive→roadmap",
    steps=[SOPStep(name="Vision", role="Strategist", description="Define product vision and North Star", instructions="3-year vision. North Star metric.", expected_output="Vision + metrics"),
           SOPStep(name="Positioning", role="Market Analyst", description="Market positioning and differentiation", instructions="Target segment. Unique value proposition.", expected_output="Positioning canvas", depends_on=["Vision"]),
           SOPStep(name="Competitive Analysis", role="Competitive Analyst", description="Analyze competitive landscape", instructions="3-5 competitors.", expected_output="Competitive matrix", depends_on=["Vision"]),
           SOPStep(name="Roadmap", role="PM Lead", description="Build outcome-focused roadmap", instructions="Quarterly outcomes. RICE.", expected_output="Outcome roadmap", depends_on=["Positioning", "Competitive Analysis"], requires_approval=True)],
    context_template="Build product strategy.", next_steps=["write_prd", "plan_launch"])

PLAYBOOK_WRITE_PRD = SOPPlaybook(name="Write PRD", description="problem→solution→specs→review",
    steps=[SOPStep(name="Problem Definition", role="PM", description="Define problem, segment, success criteria", instructions="Who, how big, success metrics.", expected_output="Problem statement"),
           SOPStep(name="Solution Design", role="Solution Architect", description="Propose solution with alternatives", instructions="Solution + rejected alternatives.", expected_output="Solution proposal", depends_on=["Problem Definition"]),
           SOPStep(name="Specifications", role="Technical Writer", description="Detailed requirements", instructions="User stories, edge cases, NFR.", expected_output="PRD document", depends_on=["Solution Design"]),
           SOPStep(name="Review", role="Reviewer", description="Review PRD", instructions="Clear problem? Measurable? Feasible?", expected_output="Review verdict", depends_on=["Specifications"], requires_approval=True)],
    context_template="Create comprehensive PRD.", next_steps=["plan_launch", "discover"])

PLAYBOOK_PLAN_LAUNCH = SOPPlaybook(name="Launch Plan", description="checklist→comms→risks→timeline",
    steps=[SOPStep(name="Launch Checklist", role="Launch PM", description="Pre-launch checklist", instructions="QA, docs, support, monitoring, rollback.", expected_output="Checklist"),
           SOPStep(name="Communications", role="Comms Lead", description="Internal and external comms", instructions="Team brief, changelog, blog.", expected_output="Comms plan", depends_on=["Launch Checklist"]),
           SOPStep(name="Risk Assessment", role="Risk Analyst", description="Launch risks and mitigations", instructions="Pre-mortem.", expected_output="Risk matrix", depends_on=["Launch Checklist"]),
           SOPStep(name="Timeline", role="Project Lead", description="Launch timeline with owners", instructions="Day-by-day. Go/no-go.", expected_output="Launch timeline", depends_on=["Communications", "Risk Assessment"], requires_approval=True)],
    context_template="Plan product launch.", next_steps=["research"])

PLAYBOOK_NORTH_STAR = SOPPlaybook(name="North Star Metric", description="identify→decompose→dashboard→align",
    steps=[SOPStep(name="Metric Identification", role="Metrics Lead", description="Identify North Star metric", instructions="Breadth, depth, frequency, efficiency.", expected_output="North Star definition"),
           SOPStep(name="Input Decomposition", role="Analyst", description="Decompose into input metrics", instructions="3-5 input metrics.", expected_output="Input metric tree", depends_on=["Metric Identification"]),
           SOPStep(name="Dashboard Design", role="Data Analyst", description="Design metrics dashboard", instructions="North Star top, inputs below.", expected_output="Dashboard spec", depends_on=["Input Decomposition"]),
           SOPStep(name="Team Alignment", role="PM Lead", description="Align team OKRs to metrics", instructions="Map OKRs to inputs.", expected_output="Alignment matrix", depends_on=["Dashboard Design"])],
    context_template="Define North Star metric.", next_steps=["strategy", "discover"])

BUILTIN_PLAYBOOKS = {"research": PLAYBOOK_RESEARCH, "code_review": PLAYBOOK_CODE_REVIEW,
    "discover": PLAYBOOK_DISCOVER, "strategy": PLAYBOOK_STRATEGY,
    "write_prd": PLAYBOOK_WRITE_PRD, "plan_launch": PLAYBOOK_PLAN_LAUNCH,
    "north_star": PLAYBOOK_NORTH_STAR}

# ── Swarm Cycle Playbooks ────────────────────────────────

PLAYBOOK_SWARM_FEATURE = SOPPlaybook(name="Swarm Feature Delivery", description="plan→implement→verify→improve for new features",
    steps=[SOPStep(name="Plan", role="PM Lead", description="Define scope, constraints, decompose tasks", instructions="Read REPO_MAP. List tasks with roles. Define success criteria. Check policies.", expected_output="Plan document with goal, tasks, criteria"),
           SOPStep(name="Implement", role="Developer", description="Execute tasks with checkpoints", instructions="Follow role rules. Checkpoint after each task. Record execution log.", expected_output="Working code + execution log", depends_on=["Plan"]),
           SOPStep(name="Verify", role="Reviewer", description="Run tests, check compliance, verify criteria", instructions="pytest + integration + harness check. Policy compliance. Success criteria.", expected_output="Check report", depends_on=["Implement"]),
           SOPStep(name="Improve", role="Analyst", description="Apply fixes, update docs, extract lessons", instructions="Fix gaps. Update docs. Extract skills. Define next cycle.", expected_output="Cycle report + next steps", depends_on=["Verify"])],
    context_template="Feature delivery using Swarm Cycle.", next_steps=["code_review"])

PLAYBOOK_SWARM_BUGFIX = SOPPlaybook(name="Swarm Bugfix", description="reproduce→fix→verify→prevent for bugs",
    steps=[SOPStep(name="Diagnose", role="Analyst", description="Reproduce bug and identify root cause", instructions="Reproduce. Identify file:line. Check recent changes.", expected_output="Root cause analysis"),
           SOPStep(name="Fix", role="Developer", description="Minimal fix + regression test", instructions="Smallest change possible. Add test that fails without fix.", expected_output="Fix + regression test", depends_on=["Diagnose"]),
           SOPStep(name="Verify", role="Reviewer", description="All tests pass, no side effects", instructions="Full test suite. Check no unintended changes.", expected_output="Verification report", depends_on=["Fix"]),
           SOPStep(name="Prevent", role="Analyst", description="Document cause, update policy if needed", instructions="Why did this happen? How to prevent? Update docs if pattern.", expected_output="Prevention notes", depends_on=["Verify"])],
    context_template="Bugfix using Swarm Cycle.", next_steps=["code_review"])

PLAYBOOK_SWARM_RESEARCH = SOPPlaybook(name="Swarm Research", description="question→gather→synthesize→extract for research",
    steps=[SOPStep(name="Define Question", role="PM Lead", description="Define research question and scope", instructions="One clear question. Time box. Source requirements.", expected_output="Research brief"),
           SOPStep(name="Gather", role="Researcher", description="Collect sources and data", instructions="3+ independent sources. Verify each. Extract key data.", expected_output="Source collection + raw findings", depends_on=["Define Question"]),
           SOPStep(name="Synthesize", role="Writer", description="Combine findings into report", instructions="Executive summary. Key findings. Recommendations. Next steps.", expected_output="Research report", depends_on=["Gather"]),
           SOPStep(name="Extract", role="Analyst", description="Extract reusable knowledge and next cycles", instructions="What skills did we learn? What follow-up research? What decisions enabled?", expected_output="Extracted skills + next cycles", depends_on=["Synthesize"])],
    context_template="Research using Swarm Cycle.", next_steps=["strategy", "write_prd"])

SWARM_PLAYBOOKS = {
    "swarm_feature": PLAYBOOK_SWARM_FEATURE,
    "swarm_bugfix": PLAYBOOK_SWARM_BUGFIX,
    "swarm_research": PLAYBOOK_SWARM_RESEARCH,
}

BUILTIN_PLAYBOOKS.update(SWARM_PLAYBOOKS)
