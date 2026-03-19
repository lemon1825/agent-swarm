"""Skill system — SkillBank, 5-gate shadow promotion, TF-IDF retrieval, per-class usefulness."""
from __future__ import annotations
import json, logging, math, os, re, tempfile, time
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from .semantic_router import SemanticRouter

try:
    import fcntl; _FCNTL = True
except ImportError:
    _FCNTL = False

logger = logging.getLogger("agent_swarm")

class SkillType(str, Enum):
    REFERENCE = "reference"; WORKFLOW = "workflow"

class SkillState(str, Enum):
    ACTIVE = "active"; SHADOW = "shadow"; INACTIVE = "inactive"; ARCHIVED = "archived"

@dataclass
class SkillManifest:
    domain: str = "general"; tags: List[str] = field(default_factory=list)
    inputs: List[str] = field(default_factory=list); outputs: List[str] = field(default_factory=list)
    skill_type: SkillType = SkillType.REFERENCE
    compatible_roles: List[str] = field(default_factory=list)
    # Ontology-aware fields
    capabilities: List[str] = field(default_factory=list)  # ontology term IDs this skill provides
    task_types: List[str] = field(default_factory=list)     # ontology task types this skill is designed for
    artifact_types: List[str] = field(default_factory=list) # ontology artifact types this skill can produce
    # Role-specific prompt templates
    prompt_templates: Dict[str, str] = field(default_factory=dict)
    # e.g. {"implementer": "You are implementing...", "reviewer": "You are reviewing..."}

    def matches_task(self, desc: str, role: str = "") -> bool:
        lo = desc.lower()
        if self.tags and any(t.lower() in lo for t in self.tags): return True
        if role and self.compatible_roles and any(r.lower() in role.lower() for r in self.compatible_roles): return True
        return False

    def provides_capability(self, cap_id: str) -> bool:
        """Check if this skill provides a specific ontology capability."""
        return cap_id in self.capabilities or cap_id in self.tags

@dataclass
class Skill:
    name: str; principle: str; when_to_apply: str
    source: str = "manual"; category: str = "general"; run_id: int = 0; version: int = 1
    state: SkillState = SkillState.ACTIVE
    hit_count: int = 0; helped_count: int = 0; failed_after: int = 0
    last_used_run: int = 0; shadow_hits: int = 0; shadow_helped: int = 0
    class_helped: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    class_failed: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    manifest: Optional[SkillManifest] = None
    # Skill Genetics: genetic individual fields
    parents: List[str] = field(default_factory=list)
    generation: int = 0
    born_from: str = ""  # "mutation", "crossover", "manual"
    origin_run_id: int = 0
    fitness: float = 0.0  # computed fitness score

    @property
    def usefulness(self): t = self.helped_count + self.failed_after; return self.helped_count / max(t, 1)
    @property
    def shadow_usefulness(self): return self.shadow_helped / max(self.shadow_hits, 1)
    def usefulness_for(self, task_class: str) -> float:
        h = self.class_helped.get(task_class, 0); f = self.class_failed.get(task_class, 0)
        if h + f == 0: return self.usefulness
        return h / max(h + f, 1)
    def get_prompt_for_role(self, role: str, context: Dict[str, str] = None) -> str:
        """Get role-specific prompt template with variable substitution."""
        if not self.manifest or role not in self.manifest.prompt_templates:
            return self.principle
        template = self.manifest.prompt_templates[role]
        if context:
            for k, v in context.items():
                template = template.replace(f"{{{k}}}", str(v))
        return template

    def to_prompt_str(self): return f"[{self.name}] {self.principle} (when: {self.when_to_apply})"
    def to_dict(self):
        d = {k: getattr(self, k) for k in self.__dataclass_fields__ if k not in ("state", "class_helped", "class_failed")}
        d["state"] = self.state.value; d["class_helped"] = dict(self.class_helped); d["class_failed"] = dict(self.class_failed)
        return d
    @classmethod
    def from_dict(cls, d):
        d2 = dict(d); d2["state"] = SkillState(d2.get("state", "active"))
        d2["class_helped"] = defaultdict(int, d2.get("class_helped", {}))
        d2["class_failed"] = defaultdict(int, d2.get("class_failed", {}))
        return cls(**{k: d2[k] for k in d2 if k in cls.__dataclass_fields__})

PERSISTENCE_VERSION = 12

class _TFIDFIndex:
    def __init__(self): self._df = Counter(); self._n = 0
    def update(self, texts):
        self._n = len(texts); self._df = Counter()
        for t in texts: self._df.update(set(self._tok(t)))
    def score(self, query, doc):
        qt = self._tok(query); dt = self._tok(doc)
        if not qt or not dt: return 0.0
        s = 0.0
        for t in qt:
            if t in dt: tf = dt.count(t) / len(dt); idf = math.log((self._n + 1) / (self._df.get(t, 1) + 1)) + 1; s += tf * idf
        qb = set(zip(qt, qt[1:])); db = set(zip(dt, dt[1:]))
        if qb and db: s += 0.3 * len(qb & db) / max(len(qb | db), 1)
        return s
    @staticmethod
    def _tok(t): return [w.lower() for w in t.split() if len(w) > 2]

class FailureCluster:
    def __init__(self):
        self._p: Dict[str, List[Dict]] = defaultdict(list)
        self._task_attempts: Dict[str, int] = defaultdict(int)
        self._escalations: List[Dict] = []

    def add(self, err, task, role):
        pat = self._norm(err)
        self._p[pat].append({"error": err, "task": task, "role": role})
        self._task_attempts[pat] += 1
        if self._task_attempts[pat] >= 3 and not self._already_escalated(pat):
            self._escalations.append({
                "task_pattern": pat,
                "attempts": self._task_attempts[pat],
                "timestamp": time.time(),
                "phase": "architecture_review_needed",
            })

    def _already_escalated(self, pat: str) -> bool:
        return any(e["task_pattern"] == pat for e in self._escalations)

    def get_escalations(self) -> List[Dict]:
        """Return tasks needing architecture review (3+ failed attempts)."""
        return list(self._escalations)

    def needs_escalation(self, err: str) -> bool:
        """Check if this error pattern has hit the escalation threshold."""
        return self._task_attempts[self._norm(err)] >= 3

    def get_clusters(self, n=2):
        return sorted([{"pattern": k, "count": len(v), "roles": list({e["role"] for e in v}), "sample": v[0]["error"]}
                        for k, v in self._p.items() if len(v) >= n], key=lambda c: -c["count"])

    @staticmethod
    def _norm(e): s = e.lower()[:80]; s = re.sub(r'\d+', 'N', s); s = re.sub(r'/[^\s]+', '/P', s); return re.sub(r'\s+', ' ', s).strip()

class SkillBank:
    def __init__(self, max_general=30, max_per_cat=15, decay_threshold=5, min_usefulness=0.2):
        self.general: List[Skill] = []; self.specific: Dict[str, List[Skill]] = defaultdict(list)
        self._mg = max_general; self._mc = max_per_cat; self._decay = decay_threshold; self._mu = min_usefulness
        self._tfidf = _TFIDFIndex(); self._fc = FailureCluster()
        self._semantic = SemanticRouter()  # auto-fallback if sentence-transformers not installed
        self._run_success_rates: List[float] = []
        self._shadow_runs: Dict[str, List[Dict]] = {}  # shadow replay data

    def retrieve(self, desc, role="", top_k=8, min_score=0.05, onto_term_id=""):
        if not desc or not desc.strip(): return []
        task_class = role.lower().split()[0] if role else ""
        return self._rank(desc, role, task_class, [s for s in self._all() if s.state == SkillState.ACTIVE], top_k, min_score, onto_term_id)
    def retrieve_shadow(self, desc, role="", top_k=4, min_score=0.05, onto_term_id=""):
        task_class = role.lower().split()[0] if role else ""
        return self._rank(desc, role, task_class, [s for s in self._all() if s.state == SkillState.SHADOW], top_k, min_score, onto_term_id)
    def _rank(self, desc, role, task_class, cands, top_k, min_score, onto_term_id=""):
        if not cands: return []
        corpus = [f"{s.when_to_apply} {s.principle}" for s in cands]
        self._tfidf.update(corpus); scored = []
        for s, doc in zip(cands, corpus):
            t = self._tfidf.score(desc, doc)
            rb = 0.3 if (role and s.category != "general" and role.lower().startswith(s.category[:4])) else (0.15 if s.category == "general" else 0.0)
            u = s.usefulness_for(task_class) if task_class else s.usefulness
            # Ontology-aware bonus: skill declares matching task_type or capability
            ob = 0.0
            if onto_term_id and s.manifest:
                if onto_term_id in s.manifest.task_types: ob = 0.4
                elif any(onto_term_id.split("/")[-1].lower() in c.lower() for c in s.manifest.capabilities): ob = 0.25
            # Semantic similarity bonus (0.0–0.35) — zero when sentence-transformers absent
            sem = self._semantic.score(desc, [doc])[0] * 0.35
            total = t + rb + u * 0.2 + ob + sem
            if total >= min_score: scored.append((total, s))
        scored.sort(key=lambda x: -x[0]); result = [s for _, s in scored[:top_k]]
        for s in result: s.hit_count += 1
        return result

    def format_for_prompt(self, skills, role=""):
        if not skills: return ""
        lines = []
        for s in skills:
            prompt = s.get_prompt_for_role(role) if role else s.to_prompt_str()
            lines.append(f"  - {prompt}")
        return "[Available Skills]\n" + "\n".join(lines)

    def add(self, skill):
        existing = self._find_dup(skill)
        if existing: self._merge(existing, skill); return False
        target = self.general if skill.category == "general" else self.specific[skill.category]
        limit = self._mg if skill.category == "general" else self._mc
        if len(target) >= limit: self._prune(target)
        if len(target) < limit: target.append(skill); return True
        return False
    def _find_dup(self, skill):
        sw = self._tok(skill.principle)
        for s in self._all():
            ew = self._tok(s.principle); u = sw | ew
            if u and len(sw & ew) / len(u) > 0.7: return s
        return None
    def _merge(self, e, n):
        e.version += 1; e.last_used_run = max(e.last_used_run, n.run_id)
        if len(n.principle) > len(e.principle): e.principle = n.principle
    def _prune(self, sk):
        if sk: w = min(sk, key=lambda s: (s.usefulness, s.hit_count)); w.state = SkillState.ARCHIVED; sk.remove(w)

    def record_active_outcome(self, skills, ok, rid, task_class="", evidence=""):
        """Record outcome with optional verification evidence.

        Args:
            evidence: Verification command output or summary (e.g. "12/12 tests passed").
                      Empty string allowed for backward compatibility.
        """
        for s in skills:
            s.last_used_run = rid
            if ok: s.helped_count += 1; (s.class_helped.__setitem__(task_class, s.class_helped.get(task_class, 0) + 1) if task_class else None)
            else: s.failed_after += 1; (s.class_failed.__setitem__(task_class, s.class_failed.get(task_class, 0) + 1) if task_class else None)
        if evidence:
            for s in skills:
                s._last_evidence = evidence
    def record_shadow_outcome(self, shadows, ok, rid, retry_count=1, latency_ms=0.0):
        for s in shadows:
            s.shadow_hits += 1
            if ok: s.shadow_helped += 1
            # Replay benchmark: track per-shadow run-level stats
            key = s.name
            self._shadow_runs.setdefault(key, []).append({
                "ok": ok, "rid": rid, "retries": retry_count, "latency": latency_ms})
    def record_run_success(self, rate: float): self._run_success_rates.append(rate)
    def _baseline_success_rate(self) -> float:
        if not self._run_success_rates: return 0.0
        return sum(self._run_success_rates) / len(self._run_success_rates)

    def compute_replay_delta(self, shadow: Skill) -> Dict:
        """Lightweight A/B comparison: runs where shadow was present vs overall baseline.
        No extra LLM calls — purely statistical from recorded outcomes."""
        key = shadow.name
        runs = self._shadow_runs.get(key, [])
        if len(runs) < 3:
            return {"sufficient_data": False, "delta": {}}
        present_ok = sum(1 for r in runs if r["ok"])
        present_rate = present_ok / len(runs)
        present_retries = sum(r["retries"] for r in runs) / len(runs)
        present_latency = sum(r["latency"] for r in runs) / len(runs)
        baseline_rate = self._baseline_success_rate()
        # Compute deltas (positive = shadow helps)
        return {
            "sufficient_data": True,
            "sample_size": len(runs),
            "delta": {
                "success_rate": round(present_rate - baseline_rate, 3) if baseline_rate > 0 else 0,
                "avg_retries": round(present_retries, 2),
                "avg_latency_ms": round(present_latency, 1),
            },
            "verdict": "positive" if present_rate > baseline_rate else ("neutral" if present_rate == baseline_rate else "negative"),
        }

    def evaluate_shadow_promotion(self, shadow: Skill, min_hits: int = 3, min_useful: float = 0.5) -> Tuple[bool, str]:
        """6-gate promotion: hits, usefulness, global baseline, class baseline, run effectiveness, replay delta."""
        if shadow.shadow_hits < min_hits: return False, f"Insufficient data ({shadow.shadow_hits}/{min_hits} hits)"
        if shadow.shadow_usefulness < min_useful: return False, f"Low usefulness ({shadow.shadow_usefulness:.0%}<{min_useful:.0%})"
        active_avg = self._avg_active_usefulness()
        if active_avg > 0 and shadow.shadow_usefulness <= active_avg * 0.8:
            return False, f"Below baseline ({shadow.shadow_usefulness:.0%} vs avg {active_avg:.0%})"
        if shadow.class_helped or shadow.class_failed:
            for cls in set(list(shadow.class_helped.keys()) + list(shadow.class_failed.keys())):
                cls_u = shadow.usefulness_for(cls); cls_avg = self._avg_class_usefulness(cls)
                if cls_avg > 0 and cls_u < cls_avg * 0.7:
                    return False, f"Below class '{cls}' baseline ({cls_u:.0%} vs {cls_avg:.0%})"
        run_baseline = self._baseline_success_rate()
        if run_baseline > 0 and shadow.shadow_usefulness < run_baseline * 0.9:
            return False, f"Below run baseline ({shadow.shadow_usefulness:.0%} vs run avg {run_baseline:.0%})"
        # Gate 6: Replay delta — shadow must not show negative impact
        delta = self.compute_replay_delta(shadow)
        if delta["sufficient_data"] and delta["verdict"] == "negative":
            return False, f"Replay delta negative: {delta['delta']}"
        return True, "Passed: 6-gate (hits, usefulness, global, class, effectiveness, replay)"

    def _avg_active_usefulness(self) -> float:
        active = [s for s in self._all() if s.state == SkillState.ACTIVE and s.hit_count > 0]
        if not active: return 0.0
        return sum(s.usefulness for s in active) / len(active)
    def _avg_class_usefulness(self, task_class: str) -> float:
        active = [s for s in self._all() if s.state == SkillState.ACTIVE and s.hit_count > 0]
        scores = [s.usefulness_for(task_class) for s in active if task_class in s.class_helped or task_class in s.class_failed]
        return sum(scores) / len(scores) if scores else 0.0

    def promote_shadows(self, min_hits=3, min_useful=0.5):
        p = r = 0
        for s in self._all():
            if s.state != SkillState.SHADOW: continue
            ok, reason = self.evaluate_shadow_promotion(s, min_hits, min_useful)
            if ok: s.state = SkillState.ACTIVE; s.helped_count = s.shadow_helped; p += 1
            elif s.shadow_hits >= min_hits: s.state = SkillState.INACTIVE; r += 1
        return {"promoted": p, "rejected": r}

    def run_lifecycle(self, rid):
        stats = {"decayed": 0, "deactivated": 0}
        for s in self._all():
            if s.state != SkillState.ACTIVE: continue
            if rid - s.last_used_run > self._decay and s.hit_count > 0: s.state = SkillState.INACTIVE; stats["decayed"] += 1
            elif s.hit_count >= 5 and s.usefulness < self._mu: s.state = SkillState.INACTIVE; stats["deactivated"] += 1
        return stats

    def record_failure(self, err, desc, role): self._fc.add(err, desc, role)
    def get_failure_patterns(self, n=2): return self._fc.get_clusters(n)

    @staticmethod
    def validate_evolution_schema(data) -> Tuple[bool, str]:
        if not isinstance(data, dict): return False, "Not dict"
        for f in ("name", "principle", "when_to_apply"):
            if f not in data or not str(data[f]).strip(): return False, f"Missing:{f}"
        if len(str(data["principle"])) < 10: return False, "Principle<10 chars"
        if len(str(data["when_to_apply"])) < 5: return False, "when_to_apply<5"
        q = int(data.get("quality_score", 0))
        if q < 5: return False, f"Quality {q}<5"
        return True, "OK"

    def save(self, path):
        data = {"_version": PERSISTENCE_VERSION, "general": [s.to_dict() for s in self.general],
                "specific": {c: [s.to_dict() for s in sl] for c, sl in self.specific.items()},
                "failure_patterns": self._fc.get_clusters(1)}
        d = os.path.dirname(path) or "."
        fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                if _FCNTL: fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                json.dump(data, f, indent=2, ensure_ascii=False); f.flush(); os.fsync(f.fileno())
            os.replace(tmp, path)
            try: dd = os.open(d, os.O_RDONLY); os.fsync(dd); os.close(dd)
            except OSError: pass
        except Exception:
            try: os.unlink(tmp)
            except OSError: pass
            raise

    def load(self, path):
        with open(path) as f:
            if _FCNTL:
                try: fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                except OSError: pass
            data = json.load(f)
        self.general = [Skill.from_dict(d) for d in data.get("general", [])]
        self.specific = defaultdict(list)
        for c, sl in data.get("specific", {}).items(): self.specific[c] = [Skill.from_dict(d) for d in sl]
        for fp in data.get("failure_patterns", []):
            for _ in range(fp.get("count", 1)): self._fc.add(fp.get("sample", fp.get("pattern", "")), "", fp.get("roles", ["?"])[0])

    def get_metrics(self):
        a = self._all(); act = [s for s in a if s.state == SkillState.ACTIVE]
        return {"total": len(a), "active": len(act), "shadow": sum(1 for s in a if s.state == SkillState.SHADOW),
                "inactive": sum(1 for s in a if s.state == SkillState.INACTIVE),
                "total_hits": sum(s.hit_count for s in a), "total_helped": sum(s.helped_count for s in a),
                "avg_usefulness": round(sum(s.usefulness for s in act) / max(len(act), 1), 3),
                "failure_patterns": len(self._fc.get_clusters(2)),
                "by_source": {src: sum(1 for s in a if s.source == src) for src in ("success", "failure", "evolution", "manual")}}

    def _all(self): return self.general + [s for sl in self.specific.values() for s in sl]
    @property
    def total_count(self): return len(self._all())
    @staticmethod
    def _tok(t): return {w.lower() for w in t.split() if len(w) > 2}
