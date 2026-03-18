"""Lightweight ontology — SKOS-style vocabulary, relations, capability routing.
RDF/OWL/SHACL → product layer. This is dataclass-only, zero deps."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

class OntologyGateMode(str, Enum):
    SOFT = "soft"       # log only
    WARN = "warn"       # log + count errors
    STRICT = "strict"   # block task

@dataclass
class OntologyViolation:
    """Structured ontology violation — first-class error object, not a string."""
    task_id: str
    violation_type: str  # capability_missing, role_mismatch, handoff_incompatible, plan_validation
    term_id: str = ""
    detail: str = ""
    missing: List[str] = field(default_factory=list)
    recommended_role: str = ""
    gate_mode: str = ""
    blocked: bool = False
    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if v}

@dataclass
class OntologyTerm:
    id: str; label: str; kind: str = "Concept"
    definition: str = ""; parents: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)

@dataclass
class OntologyRelation:
    predicate: str; subject: str; object: str

@dataclass
class OntologyBundle:
    bundle_id: str; version: str = "0.1.0"; namespace: str = "sw"
    terms: List[OntologyTerm] = field(default_factory=list)
    relations: List[OntologyRelation] = field(default_factory=list)
    competency_questions: List[str] = field(default_factory=list)  # Grüninger & Fox CQs

    @classmethod
    def from_dict(cls, data: Dict) -> 'OntologyBundle':
        """Load from dict (parsed JSON/YAML). Zero deps for JSON, optional pyyaml."""
        terms = [OntologyTerm(**t) for t in data.get("terms", [])]
        rels = [OntologyRelation(**r) for r in data.get("relations", [])]
        return cls(bundle_id=data["bundle_id"], version=data.get("version", "0.1.0"),
                   namespace=data.get("namespace", "sw"), terms=terms, relations=rels,
                   competency_questions=data.get("competency_questions", []))

    @classmethod
    def from_json_file(cls, path: str) -> 'OntologyBundle':
        """Load from JSON file. Zero external dependencies."""
        import json
        with open(path) as f:
            return cls.from_dict(json.load(f))

    @classmethod
    def from_yaml_file(cls, path: str) -> 'OntologyBundle':
        """Load from YAML file. Requires pyyaml (optional)."""
        try:
            import yaml
        except ImportError:
            raise ImportError("Install pyyaml to load YAML ontology bundles: pip install pyyaml")
        with open(path) as f:
            return cls.from_dict(yaml.safe_load(f))

    def to_dict(self) -> Dict:
        return {"bundle_id": self.bundle_id, "version": self.version, "namespace": self.namespace,
                "terms": [{"id": t.id, "label": t.label, "kind": t.kind, "definition": t.definition,
                           "parents": t.parents, "aliases": t.aliases} for t in self.terms],
                "relations": [{"predicate": r.predicate, "subject": r.subject, "object": r.object}
                              for r in self.relations],
                "competency_questions": self.competency_questions}

    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


@dataclass
class ValidationReport:
    """SHACL-inspired validation report — structured 'why it failed' for debugging/audit."""
    conforms: bool = True
    violations: List[OntologyViolation] = field(default_factory=list)
    total_checks: int = 0
    timestamp: float = 0.0

    def add(self, v: OntologyViolation):
        self.violations.append(v)
        self.conforms = False

    def to_dict(self) -> Dict:
        import time
        return {"conforms": self.conforms, "total_checks": self.total_checks,
                "violations_count": len(self.violations),
                "violations": [v.to_dict() for v in self.violations],
                "timestamp": self.timestamp or time.time()}

class OntologyRegistry:
    """Index and query ontology bundles. SKOS broaderTransitive-style ancestor closure."""
    def __init__(self, bundles: List[OntologyBundle] = None):
        self._terms: Dict[str, OntologyTerm] = {}
        self._parents: Dict[str, Set[str]] = defaultdict(set)
        self._requires: Dict[str, Set[str]] = defaultdict(set)
        self._produces: Dict[str, Set[str]] = defaultdict(set)
        self._approval: Dict[str, str] = {}
        self._next: Dict[str, Set[str]] = defaultdict(set)
        if bundles:
            for b in bundles: self.load_bundle(b)

    def load_bundle(self, b: OntologyBundle):
        for t in b.terms:
            self._terms[t.id] = t
            for p in t.parents: self._parents[t.id].add(p)
        for r in b.relations:
            if "requires" in r.predicate: self._requires[r.subject].add(r.object)
            elif "produces" in r.predicate: self._produces[r.subject].add(r.object)
            elif "approval" in r.predicate: self._approval[r.subject] = r.object
            elif "next_task" in r.predicate: self._next[r.subject].add(r.object)

    def get_term(self, term_id: str) -> Optional[OntologyTerm]: return self._terms.get(term_id)

    def ancestors(self, term_id: str) -> Set[str]:
        out = set(); stack = list(self._parents.get(term_id, set()))
        while stack:
            x = stack.pop()
            if x not in out: out.add(x); stack.extend(self._parents.get(x, set()))
        return out

    def task_requires(self, task_type: str) -> Set[str]:
        caps = set(self._requires.get(task_type, set()))
        for a in self.ancestors(task_type): caps |= self._requires.get(a, set())
        return caps

    def task_produces(self, task_type: str) -> Set[str]:
        return set(self._produces.get(task_type, set()))

    def needs_approval(self, task_type: str) -> bool:
        if task_type in self._approval: return True
        return any(a in self._approval for a in self.ancestors(task_type))

    def validate_task_capabilities(self, task_type: str, available_caps: Set[str]) -> Tuple[bool, Set[str]]:
        required = self.task_requires(task_type)
        missing = required - available_caps
        return len(missing) == 0, missing

    def resolve_by_label(self, label: str) -> Optional[OntologyTerm]:
        lo = label.lower()
        # Exact match
        for t in self._terms.values():
            tl = t.label.lower()
            if tl == lo: return t
            if any(a.lower() == lo for a in t.aliases): return t
        # Prefix/stem match: "researcher" matches "research", "analyst" matches "analysis"
        for t in self._terms.values():
            tl = t.label.lower()
            if lo.startswith(tl) or tl.startswith(lo): return t
            if any(lo.startswith(a.lower()) or a.lower().startswith(lo) for a in t.aliases): return t
        # Shared-stem match (first 4+ chars): "analyst"↔"analysis" share "analy"
        if len(lo) >= 4:
            for t in self._terms.values():
                tl = t.label.lower()
                stem = min(len(lo), len(tl), max(4, min(len(lo), len(tl)) - 2))
                if lo[:stem] == tl[:stem]: return t
        return None

    def recommend_next(self, completed_task_type: str) -> List[str]:
        nexts = list(self._next.get(completed_task_type, set()))
        produced = self.task_produces(completed_task_type)
        for tid, reqs in self._requires.items():
            if produced & reqs and tid != completed_task_type:
                if tid not in nexts: nexts.append(tid)
        return nexts

    def detect_role_mismatch(self, task_type: str, assigned_role: str) -> Optional[str]:
        term = self.get_term(task_type) or self.resolve_by_label(assigned_role)
        if not term: return None
        role_lo = assigned_role.lower(); term_lo = term.label.lower()
        # Direct match
        if term_lo in role_lo or role_lo in term_lo: return None
        # Alias match
        for a in term.aliases:
            if a.lower() in role_lo: return None
        # Stem match (same first 4+ chars): "analyst"↔"analysis"
        if len(role_lo) >= 4 and len(term_lo) >= 4:
            stem = min(len(role_lo), len(term_lo), max(4, min(len(role_lo), len(term_lo)) - 2))
            if role_lo[:stem] == term_lo[:stem]: return None
        return f"Role '{assigned_role}' may not match task type '{term.label}'"

    def get_stats(self) -> Dict:
        return {"terms": len(self._terms),
                "relations": sum(len(v) for v in self._requires.values()) + sum(len(v) for v in self._produces.values()) + len(self._approval) + sum(len(v) for v in self._next.values()),
                "task_types": len(self._requires), "approval_policies": len(self._approval)}

    # ================================================================
    #  Ontology-driven Planner / Recommendation
    # ================================================================

    def recommend_role(self, task_description: str) -> Optional[str]:
        """Given a task description, recommend the best ontology-matched role."""
        desc_lo = task_description.lower(); desc_words = desc_lo.split()
        best_term = None; best_score = 0
        for term in self._terms.values():
            if "TaskType" not in term.id: continue
            score = 0; tl = term.label.lower()
            if tl in desc_lo: score += 5
            for w in desc_words:
                if len(w) >= 4 and len(tl) >= 4 and w[:4] == tl[:4]: score += 4
            for a in term.aliases:
                if a.lower() in desc_lo: score += 3
            if term.definition:
                for w in term.definition.lower().split():
                    if len(w) > 3 and w in desc_lo: score += 1
            if score > best_score: best_score = score; best_term = term
        return best_term.label if best_term and best_score > 0 else None

    def recommend_playbook(self, goal: str, playbooks: Dict) -> List[Dict]:
        """Score playbooks against a goal using ontology term matching.
        Returns sorted list of {name, score, reason}."""
        goal_lo = goal.lower()
        scored = []
        for name, pb in playbooks.items():
            score = 0; reasons = []
            # Match playbook description against ontology terms
            pb_text = (pb.description if hasattr(pb, 'description') else str(pb)).lower()
            for term in self._terms.values():
                if "TaskType" not in term.id: continue
                tl = term.label.lower()
                # Goal mentions this task type
                if tl in goal_lo:
                    score += 2; reasons.append(f"goal matches '{term.label}'")
                # Playbook involves this task type
                if tl in pb_text:
                    score += 1
                # Alias match in goal
                for a in term.aliases:
                    if a.lower() in goal_lo: score += 1; reasons.append(f"alias '{a}'")
            # Playbook name direct match
            if name.lower() in goal_lo: score += 3; reasons.append("name match")
            scored.append({"name": name, "score": score, "reason": "; ".join(reasons[:3])})
        return sorted(scored, key=lambda x: -x["score"])

    def score_task_role_fit(self, task_description: str, role: str) -> float:
        """Score 0.0-1.0 how well a role fits a task, based on ontology.
        Used by planner to assign optimal roles."""
        # Resolve task → term (with stem matching)
        desc_lo = task_description.lower(); desc_words = desc_lo.split()
        best_term = None; best_score = 0
        for term in self._terms.values():
            if "TaskType" not in term.id: continue
            s = 0; tl = term.label.lower()
            if tl in desc_lo: s += 5
            for w in desc_words:
                if len(w) >= 4 and len(tl) >= 4 and w[:4] == tl[:4]: s += 4
            for a in term.aliases:
                if a.lower() in desc_lo: s += 3
            if term.definition:
                for w in term.definition.lower().split():
                    if len(w) > 3 and w in desc_lo: s += 1
            if s > best_score: best_score = s; best_term = term
        if not best_term: return 0.3  # no match = neutral

        # Check if role matches the term
        mismatch = self.detect_role_mismatch(best_term.id, role)
        if mismatch is None: return 1.0  # perfect match

        # Partial match: check ancestors
        role_term = self.resolve_by_label(role)
        if role_term and best_term.id in self.ancestors(role_term.id):
            return 0.7  # ancestor match = decent

        return 0.2  # no match

    def validate_plan_report(self, tasks: Dict, skill_caps: set = None) -> 'ValidationReport':
        """SHACL-inspired plan validation. Returns structured ValidationReport.
        Unlike _validate_plan_ontology in core.py (which returns strings),
        this returns typed OntologyViolation objects with recommended fixes."""
        import time
        report = ValidationReport(timestamp=time.time())
        if skill_caps is None: skill_caps = set()
        for tid, task in tasks.items():
            report.total_checks += 1
            tc = task.role.lower().split()[0] if hasattr(task, 'role') and task.role else ""
            term = self.resolve_by_label(tc) or self.resolve_by_label(getattr(task, 'role', ''))
            if not term:
                rec = self.recommend_role(getattr(task, 'description', ''))
                report.add(OntologyViolation(
                    task_id=tid, violation_type="role_not_found",
                    detail=f"Role '{getattr(task, 'role', '')}' not in ontology",
                    recommended_role=rec or "", gate_mode="", blocked=False))
                continue
            required = self.task_requires(term.id)
            missing = required - skill_caps
            if missing:
                report.add(OntologyViolation(
                    task_id=tid, violation_type="capability_missing",
                    term_id=term.id, detail=f"Missing capabilities for '{term.label}'",
                    missing=sorted(missing), blocked=False))
            mismatch = self.detect_role_mismatch(term.id, getattr(task, 'role', ''))
            if mismatch:
                rec = self.recommend_role(getattr(task, 'description', ''))
                report.add(OntologyViolation(
                    task_id=tid, violation_type="role_mismatch",
                    term_id=term.id, detail=mismatch,
                    recommended_role=rec or "", blocked=False))
        return report

    def check_competency_questions(self, bundles: List['OntologyBundle'] = None) -> Dict:
        """Grüninger & Fox: verify the ontology can answer its declared questions.
        Returns {question: bool, ...} for each CQ in loaded bundles."""
        results = {}
        cqs = []
        if bundles:
            for b in bundles: cqs.extend(b.competency_questions)
        # Map common CQ patterns to registry capabilities
        cq_checks = {
            "require": lambda: len(self._requires) > 0,
            "produce": lambda: len(self._produces) > 0,
            "role": lambda: any("TaskType" in t.id for t in self._terms.values()),
            "approval": lambda: len(self._approval) > 0,
            "next": lambda: len(self._next) > 0,
            "ancestor": lambda: any(len(p) > 0 for p in self._parents.values()),
            "capabilit": lambda: len(self._requires) > 0,
            "validat": lambda: len(self._requires) > 0,
            "skill": lambda: len(self._requires) > 0,
        }
        for cq in cqs:
            cq_lo = cq.lower()
            answered = False
            for key, check in cq_checks.items():
                if key in cq_lo:
                    answered = check()
                    break
            if not answered:
                # Generic: can we resolve any term mentioned in the question?
                words = cq_lo.split()
                answered = any(self.resolve_by_label(w) is not None for w in words if len(w) > 3)
            results[cq] = answered
        return results

CORE_ONTOLOGY = OntologyBundle(bundle_id="core-vocab", version="0.1.0", namespace="sw",
    terms=[
        OntologyTerm(id="sw:TaskType/Research", label="Research", definition="Gather sources and produce summary", aliases=["조사", "리서치"]),
        OntologyTerm(id="sw:TaskType/Analysis", label="Analysis", definition="Analyze data and identify patterns", parents=["sw:TaskType/Research"], aliases=["분석"]),
        OntologyTerm(id="sw:TaskType/Writing", label="Writing", definition="Produce written deliverable", aliases=["작성"]),
        OntologyTerm(id="sw:TaskType/Review", label="Review", definition="Verify quality and correctness", aliases=["검토", "리뷰"]),
        OntologyTerm(id="sw:TaskType/Strategy", label="Strategy", definition="Define vision, positioning, roadmap", aliases=["전략"]),
        OntologyTerm(id="sw:SkillCap/WebSearch", label="Web Search", kind="Class"),
        OntologyTerm(id="sw:SkillCap/DataAnalysis", label="Data Analysis", kind="Class"),
        OntologyTerm(id="sw:SkillCap/TextGeneration", label="Text Generation", kind="Class"),
        OntologyTerm(id="sw:SkillCap/CodeAnalysis", label="Code Analysis", kind="Class"),
        OntologyTerm(id="sw:ArtifactType/Summary", label="Summary"),
        OntologyTerm(id="sw:ArtifactType/Report", label="Report"),
        OntologyTerm(id="sw:ArtifactType/PRD", label="PRD"),
    ],
    relations=[
        OntologyRelation("sw:requires", "sw:TaskType/Research", "sw:SkillCap/WebSearch"),
        OntologyRelation("sw:requires", "sw:TaskType/Analysis", "sw:SkillCap/DataAnalysis"),
        OntologyRelation("sw:requires", "sw:TaskType/Writing", "sw:SkillCap/TextGeneration"),
        OntologyRelation("sw:requires", "sw:TaskType/Review", "sw:SkillCap/CodeAnalysis"),
        OntologyRelation("sw:produces", "sw:TaskType/Research", "sw:ArtifactType/Summary"),
        OntologyRelation("sw:produces", "sw:TaskType/Writing", "sw:ArtifactType/Report"),
        OntologyRelation("sw:produces", "sw:TaskType/Strategy", "sw:ArtifactType/PRD"),
        OntologyRelation("sw:approval_required", "sw:TaskType/Strategy", "sw:Policy/ManagerApproval"),
        OntologyRelation("sw:next_task", "sw:TaskType/Research", "sw:TaskType/Analysis"),
        OntologyRelation("sw:next_task", "sw:TaskType/Analysis", "sw:TaskType/Writing"),
        OntologyRelation("sw:next_task", "sw:TaskType/Strategy", "sw:TaskType/Writing"),
        OntologyRelation("sw:next_task", "sw:TaskType/Writing", "sw:TaskType/Review"),
    ],
    competency_questions=[
        "What capabilities does a task require?",
        "What artifacts does a task produce?",
        "Which role is recommended for a task?",
        "Is approval required for this task type?",
        "What is the next step after this task?",
        "Does the ancestor closure include inherited capabilities?",
        "Can we validate task capabilities against available skills?",
    ])
