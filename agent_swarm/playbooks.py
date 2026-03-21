"""SOP Playbooks — 7 built-in workflow templates."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from typing import Any, Optional

@dataclass(frozen=True)
class SOPStep:
    name: str; role: str; description: str; instructions: str = ""
    expected_output: str = ""; depends_on: Tuple[str, ...] = ()
    output_must_contain: Tuple[str, ...] = ()
    requires_approval: bool = False
    gate: Optional[Dict[str, Any]] = None
    # gate format: {"type": "approval|keyword|custom", "condition": "...", "block_message": "..."}

@dataclass(frozen=True)
class SOPPlaybook:
    name: str; description: str; steps: Tuple[SOPStep, ...] = ()
    context_template: str = ""; next_steps: Tuple[str, ...] = ()
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
    steps=(SOPStep(name="Research", role="Researcher", description="Gather data", instructions="Find 3+ sources.", expected_output="Findings"),
           SOPStep(name="Analysis", role="Analyst", description="Analyze findings", instructions="Identify patterns.", expected_output="Insights", depends_on=("Research",)),
           SOPStep(name="Verification", role="Fact Checker", description="Cross-verify", instructions="Check claims.", expected_output="Verification report", depends_on=("Analysis",)),
           SOPStep(name="Writing", role="Writer", description="Final report", instructions="Intro→Findings→Conclusion.", expected_output="Report", depends_on=("Verification",))),
    context_template="Follow SOP: research→analyze→verify→write.", next_steps=("strategy", "write_prd"))

PLAYBOOK_CODE_REVIEW = SOPPlaybook(name="Code Review", description="analysis→security→report",
    steps=(SOPStep(name="Static Analysis", role="Code Analyst", description="Code structure", instructions="Check complexity.", expected_output="Issue list"),
           SOPStep(name="Security Audit", role="Security Reviewer", description="Vulnerabilities", instructions="Check injection/auth.", expected_output="Findings", depends_on=("Static Analysis",)),
           SOPStep(name="Quality Report", role="Quality Lead", description="Synthesize", instructions="Prioritize.", expected_output="Report", depends_on=("Static Analysis", "Security Audit"))),
    next_steps=("plan_launch",))

PLAYBOOK_DISCOVER = SOPPlaybook(name="Product Discovery", description="ideate→assumptions→prioritize→experiment",
    steps=(SOPStep(name="Ideation", role="PM Ideator", description="Brainstorm ideas from PM, Designer, Engineer perspectives", instructions="Generate 10+ ideas.", expected_output="Idea list with rationale"),
           SOPStep(name="Assumptions", role="Risk Analyst", description="Identify risky assumptions across Value, Usability, Viability, Feasibility", instructions="Map each idea to assumptions.", expected_output="Assumption map", depends_on=("Ideation",)),
           SOPStep(name="Prioritization", role="Strategist", description="Prioritize assumptions by risk and impact", instructions="Use ICE or RICE. Rank top 5.", expected_output="Prioritized list", depends_on=("Assumptions",)),
           SOPStep(name="Experiment Design", role="Experiment Designer", description="Design lean experiments for top assumptions", instructions="Hypothesis, method, metric, timeline.", expected_output="Experiment plan", depends_on=("Prioritization",))),
    context_template="Run full product discovery cycle.", next_steps=("strategy", "write_prd"))

PLAYBOOK_STRATEGY = SOPPlaybook(name="Product Strategy", description="vision→positioning→competitive→roadmap",
    steps=(SOPStep(name="Vision", role="Strategist", description="Define product vision and North Star", instructions="3-year vision. North Star metric.", expected_output="Vision + metrics"),
           SOPStep(name="Positioning", role="Market Analyst", description="Market positioning and differentiation", instructions="Target segment. Unique value proposition.", expected_output="Positioning canvas", depends_on=("Vision",)),
           SOPStep(name="Competitive Analysis", role="Competitive Analyst", description="Analyze competitive landscape", instructions="3-5 competitors.", expected_output="Competitive matrix", depends_on=("Vision",)),
           SOPStep(name="Roadmap", role="PM Lead", description="Build outcome-focused roadmap", instructions="Quarterly outcomes. RICE.", expected_output="Outcome roadmap", depends_on=("Positioning", "Competitive Analysis"), requires_approval=True)),
    context_template="Build product strategy.", next_steps=("write_prd", "plan_launch"))

PLAYBOOK_WRITE_PRD = SOPPlaybook(name="Write PRD", description="problem→solution→specs→review",
    steps=(SOPStep(name="Problem Definition", role="PM", description="Define problem, segment, success criteria", instructions="Who, how big, success metrics.", expected_output="Problem statement"),
           SOPStep(name="Solution Design", role="Solution Architect", description="Propose solution with alternatives", instructions="Solution + rejected alternatives.", expected_output="Solution proposal", depends_on=("Problem Definition",)),
           SOPStep(name="Specifications", role="Technical Writer", description="Detailed requirements", instructions="User stories, edge cases, NFR.", expected_output="PRD document", depends_on=("Solution Design",)),
           SOPStep(name="Review", role="Reviewer", description="Review PRD", instructions="Clear problem? Measurable? Feasible?", expected_output="Review verdict", depends_on=("Specifications",), requires_approval=True)),
    context_template="Create comprehensive PRD.", next_steps=("plan_launch", "discover"))

PLAYBOOK_PLAN_LAUNCH = SOPPlaybook(name="Launch Plan", description="checklist→comms→risks→timeline",
    steps=(SOPStep(name="Launch Checklist", role="Launch PM", description="Pre-launch checklist", instructions="QA, docs, support, monitoring, rollback.", expected_output="Checklist"),
           SOPStep(name="Communications", role="Comms Lead", description="Internal and external comms", instructions="Team brief, changelog, blog.", expected_output="Comms plan", depends_on=("Launch Checklist",)),
           SOPStep(name="Risk Assessment", role="Risk Analyst", description="Launch risks and mitigations", instructions="Pre-mortem.", expected_output="Risk matrix", depends_on=("Launch Checklist",)),
           SOPStep(name="Timeline", role="Project Lead", description="Launch timeline with owners", instructions="Day-by-day. Go/no-go.", expected_output="Launch timeline", depends_on=("Communications", "Risk Assessment"), requires_approval=True)),
    context_template="Plan product launch.", next_steps=("research",))

PLAYBOOK_NORTH_STAR = SOPPlaybook(name="North Star Metric", description="identify→decompose→dashboard→align",
    steps=(SOPStep(name="Metric Identification", role="Metrics Lead", description="Identify North Star metric", instructions="Breadth, depth, frequency, efficiency.", expected_output="North Star definition"),
           SOPStep(name="Input Decomposition", role="Analyst", description="Decompose into input metrics", instructions="3-5 input metrics.", expected_output="Input metric tree", depends_on=("Metric Identification",)),
           SOPStep(name="Dashboard Design", role="Data Analyst", description="Design metrics dashboard", instructions="North Star top, inputs below.", expected_output="Dashboard spec", depends_on=("Input Decomposition",)),
           SOPStep(name="Team Alignment", role="PM Lead", description="Align team OKRs to metrics", instructions="Map OKRs to inputs.", expected_output="Alignment matrix", depends_on=("Dashboard Design",))),
    context_template="Define North Star metric.", next_steps=("strategy", "discover"))

BUILTIN_PLAYBOOKS = {"research": PLAYBOOK_RESEARCH, "code_review": PLAYBOOK_CODE_REVIEW,
    "discover": PLAYBOOK_DISCOVER, "strategy": PLAYBOOK_STRATEGY,
    "write_prd": PLAYBOOK_WRITE_PRD, "plan_launch": PLAYBOOK_PLAN_LAUNCH,
    "north_star": PLAYBOOK_NORTH_STAR}

# ── Swarm Cycle Playbooks ────────────────────────────────

PLAYBOOK_SWARM_FEATURE = SOPPlaybook(name="Swarm Feature Delivery", description="plan→implement→verify→improve for new features",
    steps=(SOPStep(name="Plan", role="PM Lead", description="Define scope, constraints, decompose tasks", instructions="Read REPO_MAP. List tasks with roles. Define success criteria. Check policies.", expected_output="Plan document with goal, tasks, criteria"),
           SOPStep(name="Implement", role="Developer", description="Execute tasks with checkpoints", instructions="Follow role rules. Checkpoint after each task. Record execution log.", expected_output="Working code + execution log", depends_on=("Plan",)),
           SOPStep(name="Verify", role="Reviewer", description="Run tests, check compliance, verify criteria", instructions="pytest + integration + harness check. Policy compliance. Success criteria.", expected_output="Check report", depends_on=("Implement",)),
           SOPStep(name="Improve", role="Analyst", description="Apply fixes, update docs, extract lessons", instructions="Fix gaps. Update docs. Extract skills. Define next cycle.", expected_output="Cycle report + next steps", depends_on=("Verify",))),
    context_template="Feature delivery using Swarm Cycle.", next_steps=("code_review",))

PLAYBOOK_SWARM_BUGFIX = SOPPlaybook(name="Swarm Bugfix", description="reproduce→fix→verify→prevent for bugs",
    steps=(SOPStep(name="Diagnose", role="Analyst", description="Reproduce bug and identify root cause", instructions="Reproduce. Identify file:line. Check recent changes.", expected_output="Root cause analysis"),
           SOPStep(name="Fix", role="Developer", description="Minimal fix + regression test", instructions="Smallest change possible. Add test that fails without fix.", expected_output="Fix + regression test", depends_on=("Diagnose",)),
           SOPStep(name="Verify", role="Reviewer", description="All tests pass, no side effects", instructions="Full test suite. Check no unintended changes.", expected_output="Verification report", depends_on=("Fix",)),
           SOPStep(name="Prevent", role="Analyst", description="Document cause, update policy if needed", instructions="Why did this happen? How to prevent? Update docs if pattern.", expected_output="Prevention notes", depends_on=("Verify",))),
    context_template="Bugfix using Swarm Cycle.", next_steps=("code_review",))

PLAYBOOK_SWARM_RESEARCH = SOPPlaybook(name="Swarm Research", description="question→gather→synthesize→extract for research",
    steps=(SOPStep(name="Define Question", role="PM Lead", description="Define research question and scope", instructions="One clear question. Time box. Source requirements.", expected_output="Research brief"),
           SOPStep(name="Gather", role="Researcher", description="Collect sources and data", instructions="3+ independent sources. Verify each. Extract key data.", expected_output="Source collection + raw findings", depends_on=("Define Question",)),
           SOPStep(name="Synthesize", role="Writer", description="Combine findings into report", instructions="Executive summary. Key findings. Recommendations. Next steps.", expected_output="Research report", depends_on=("Gather",)),
           SOPStep(name="Extract", role="Analyst", description="Extract reusable knowledge and next cycles", instructions="What skills did we learn? What follow-up research? What decisions enabled?", expected_output="Extracted skills + next cycles", depends_on=("Synthesize",))),
    context_template="Research using Swarm Cycle.", next_steps=("strategy", "write_prd"))

SWARM_PLAYBOOKS = {
    "swarm_feature": PLAYBOOK_SWARM_FEATURE,
    "swarm_bugfix": PLAYBOOK_SWARM_BUGFIX,
    "swarm_research": PLAYBOOK_SWARM_RESEARCH,
}

BUILTIN_PLAYBOOKS.update(SWARM_PLAYBOOKS)

# ── Additional Playbooks ────────────────────────────────

PLAYBOOK_BRAINSTORM_SPEC = SOPPlaybook(
    name="brainstorm_spec",
    description="Multi-perspective brainstorming to specification",
    steps=(
        SOPStep(name="Diverge", role="Creative Lead", description="Generate diverse ideas from multiple perspectives", expected_output="idea_list"),
        SOPStep(name="Evaluate", role="Critic", description="Evaluate ideas against feasibility and impact", depends_on=("Diverge",), expected_output="evaluation_matrix"),
        SOPStep(name="Synthesize", role="Architect", description="Synthesize top ideas into specification", depends_on=("Evaluate",), expected_output="specification_draft"),
        SOPStep(name="Review", role="Reviewer", description="Review specification for completeness", depends_on=("Synthesize",), expected_output="final_specification", requires_approval=True),
    ),
)

PLAYBOOK_SHIP = SOPPlaybook(
    name="ship",
    description="Ship pipeline: test, review, version, commit, push",
    steps=(
        SOPStep(name="Test", role="QA Engineer", description="Run all tests and verify passing", expected_output="test_results"),
        SOPStep(name="Review", role="Reviewer", description="Code review gate", depends_on=("Test",), expected_output="review_result"),
        SOPStep(name="Version", role="Release Manager", description="Bump version number", depends_on=("Review",), expected_output="version_bump"),
        SOPStep(name="Commit", role="Developer", description="Create commit with changelog", depends_on=("Version",), expected_output="commit_hash"),
        SOPStep(name="Push", role="Release Manager", description="Push to remote", depends_on=("Commit",), expected_output="push_result", requires_approval=True),
    ),
)

PLAYBOOK_QA = SOPPlaybook(
    name="qa",
    description="QA analysis with issue taxonomy and health scoring",
    steps=(
        SOPStep(name="Scan", role="QA Analyst", description="Scan codebase for issues", expected_output="raw_issues"),
        SOPStep(name="Classify", role="QA Lead", description="Classify issues by severity and category", depends_on=("Scan",), expected_output="classified_issues"),
        SOPStep(name="Score", role="QA Lead", description="Calculate health score", depends_on=("Classify",), expected_output="health_score"),
        SOPStep(name="Report", role="QA Lead", description="Generate QA report with recommendations", depends_on=("Score",), expected_output="qa_report"),
    ),
)

PLAYBOOK_RETRO = SOPPlaybook(
    name="retro",
    description="Retrospective analysis with lessons learned",
    steps=(
        SOPStep(name="Collect", role="Analyst", description="Collect metrics and telemetry data", expected_output="raw_metrics"),
        SOPStep(name="Analyze", role="Analyst", description="Analyze patterns and trends", depends_on=("Collect",), expected_output="pattern_analysis"),
        SOPStep(name="Suggest", role="Coach", description="Generate improvement suggestions", depends_on=("Analyze",), expected_output="suggestions"),
        SOPStep(name="Document", role="Writer", description="Document lessons and action items", depends_on=("Suggest",), expected_output="retro_report"),
    ),
)

BUILTIN_PLAYBOOKS.update({
    "brainstorm_spec": PLAYBOOK_BRAINSTORM_SPEC,
    "ship": PLAYBOOK_SHIP,
    "qa": PLAYBOOK_QA,
    "retro": PLAYBOOK_RETRO,
})


# ── Blueprint Registry (NVIDIA AI Factory pattern) ──────────────

@dataclass(frozen=True)
class BlueprintMetadata:
    """Metadata for a validated Blueprint (extends SOPPlaybook).

    Like a factory's certified production line: a Blueprint is a playbook
    that has been validated, versioned, and proven to work reliably.
    """
    version: str = "1.0.0"
    author: str = ""
    validated: bool = False
    tags: tuple = ()
    test_results: tuple = ()  # ("12/12 passed", "avg_score=0.85")
    description: str = ""


@dataclass(frozen=True)
class Blueprint:
    """A validated, versioned playbook with metadata.

    A validated, versioned playbook with metadata. Pre-built, customizable
    workflow templates that are tested and validated before deployment.
    """
    playbook: SOPPlaybook
    metadata: BlueprintMetadata = field(default_factory=BlueprintMetadata)

    @property
    def name(self) -> str:
        return self.playbook.name

    @property
    def is_validated(self) -> bool:
        return self.metadata.validated


class BlueprintRegistry:
    """Registry of validated Blueprints with versioning and search.

    Like a factory's catalog of certified production processes:
    register, search, and retrieve validated workflow templates.
    """

    def __init__(self):
        self._blueprints: Dict[str, Blueprint] = {}

    def register(self, key: str, blueprint: Blueprint) -> None:
        """Register a Blueprint."""
        self._blueprints[key] = blueprint

    def get(self, key: str) -> Optional[Blueprint]:
        """Get a Blueprint by key."""
        return self._blueprints.get(key)

    def list_all(self) -> Dict[str, Blueprint]:
        """List all registered Blueprints."""
        return dict(self._blueprints)

    def list_validated(self) -> Dict[str, Blueprint]:
        """List only validated Blueprints."""
        return {k: b for k, b in self._blueprints.items() if b.is_validated}

    def search_by_tag(self, tag: str) -> List[Blueprint]:
        """Find Blueprints by tag."""
        return [b for b in self._blueprints.values() if tag in b.metadata.tags]

    def from_playbook(self, key: str, playbook: SOPPlaybook,
                      version: str = "1.0.0", validated: bool = False,
                      tags: tuple = (), author: str = "") -> Blueprint:
        """Create and register a Blueprint from an existing playbook."""
        bp = Blueprint(
            playbook=playbook,
            metadata=BlueprintMetadata(
                version=version,
                validated=validated,
                tags=tags,
                author=author,
                description=playbook.description,
            ),
        )
        self.register(key, bp)
        return bp

    @property
    def count(self) -> int:
        return len(self._blueprints)


class BlueprintValidator:
    """Validates Blueprints by dry-running their step structure.

    Like a factory's quality control line: runs the production process
    with test materials before certifying the line for real production.
    """

    @staticmethod
    def validate(blueprint: Blueprint) -> Tuple[bool, List[str]]:
        """Validate a Blueprint's structural integrity.

        Checks:
        - All steps have name, role, description
        - Dependencies reference valid step names
        - No circular dependencies
        - At least one step exists

        Returns:
            (passed, issues): True if valid, list of issues found
        """
        issues: List[str] = []
        pb = blueprint.playbook

        if not pb.steps:
            issues.append("No steps defined")
            return False, issues

        step_names = {s.name for s in pb.steps}

        for step in pb.steps:
            if not step.name:
                issues.append("Step missing name")
            if not step.role:
                issues.append(f"Step '{step.name}' missing role")
            if not step.description:
                issues.append(f"Step '{step.name}' missing description")

            for dep in step.depends_on:
                if dep not in step_names:
                    issues.append(f"Step '{step.name}' depends on unknown step '{dep}'")

        # Cycle detection via topological sort
        visited = set()
        in_progress = set()

        def has_cycle(name):
            if name in in_progress:
                return True
            if name in visited:
                return False
            in_progress.add(name)
            step = next((s for s in pb.steps if s.name == name), None)
            if step:
                for dep in step.depends_on:
                    if has_cycle(dep):
                        return True
            in_progress.discard(name)
            visited.add(name)
            return False

        for s in pb.steps:
            if has_cycle(s.name):
                issues.append(f"Circular dependency detected involving '{s.name}'")
                break

        return len(issues) == 0, issues

    @staticmethod
    def validate_and_certify(registry: 'BlueprintRegistry', key: str) -> Tuple[bool, List[str]]:
        """Validate a Blueprint and update its certification status.

        If validation passes, creates a new Blueprint with validated=True
        and replaces the old one in the registry.

        Returns:
            (passed, issues)
        """
        bp = registry.get(key)
        if bp is None:
            return False, [f"Blueprint '{key}' not found"]

        passed, issues = BlueprintValidator.validate(bp)

        if passed:
            certified = Blueprint(
                playbook=bp.playbook,
                metadata=BlueprintMetadata(
                    version=bp.metadata.version,
                    author=bp.metadata.author,
                    validated=True,
                    tags=bp.metadata.tags,
                    test_results=(f"structural_check: {len(bp.playbook.steps)} steps OK",),
                    description=bp.metadata.description,
                ),
            )
            registry.register(key, certified)

        return passed, issues


# Pre-built registry with all built-in playbooks as Blueprints
BLUEPRINT_REGISTRY = BlueprintRegistry()
for _key, _playbook in BUILTIN_PLAYBOOKS.items():
    BLUEPRINT_REGISTRY.from_playbook(
        _key, _playbook,
        version="1.0.0", validated=True,
        tags=("builtin",), author="agent-swarm",
    )
