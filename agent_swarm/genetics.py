"""Skill Genetics — skill-level evolution model.

Existing agent evolution systems evolve agents, workflows, or reasoning trajectories.
Agent Swarm evolves skills themselves: each skill is an individual in a population
that mutates, recombines, competes, and is promoted only after replay and adversarial
evaluation.

Operators: mutation (in SkillBank._evolve), crossover, selection, adversarial test.
Data: fitness function, lineage tracking, population model per task-class.
"""
from __future__ import annotations
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .skills import Skill, SkillBank, SkillState


# ================================================================
#  Fitness Function
# ================================================================

@dataclass
class FitnessWeights:
    """Tunable weights for fitness computation."""
    success_rate: float = 0.30
    retry_reduction: float = 0.15
    latency_bonus: float = 0.10
    validation_pass: float = 0.15
    task_class_fit: float = 0.15
    adversarial_robustness: float = 0.15


def compute_fitness(skill: Skill, bank: SkillBank, adv_score: float = 1.0,
                    weights: FitnessWeights = None) -> float:
    """Composite fitness 0.0-1.0. This makes it genetics, not heuristic."""
    w = weights or FitnessWeights()
    sr = skill.usefulness
    replay = bank._shadow_runs.get(skill.name, [])
    retry_score = max(0, 1 - (sum(r["retries"] for r in replay) / len(replay) - 1) / 3) if replay else 0.5
    latency_score = max(0, min(1, 1 - (sum(r["latency"] for r in replay) / len(replay)) / 5000)) if replay else 0.5
    val_score = sr
    if skill.class_helped:
        best = max(skill.class_helped.values()) if skill.class_helped else 0
        total = sum(skill.class_helped.values()) + sum(skill.class_failed.values())
        class_score = best / max(total, 1)
    else:
        class_score = 0.3
    adv = min(adv_score, 1.0)
    return round(min(max(
        w.success_rate * sr + w.retry_reduction * retry_score + w.latency_bonus * latency_score +
        w.validation_pass * val_score + w.task_class_fit * class_score +
        w.adversarial_robustness * adv, 0.0), 1.0), 3)


# ================================================================
#  Lineage Record
# ================================================================

@dataclass
class LineageRecord:
    skill_name: str; born_from: str = "manual"
    parent_names: List[str] = field(default_factory=list)
    generation: int = 0; origin_run_id: int = 0
    birth_time: float = field(default_factory=time.time)
    fitness_history: List[float] = field(default_factory=list)
    promotions: int = 0; demotions: int = 0
    adversarial_tests: int = 0; adversarial_passes: int = 0
    cause_of_death: str = ""
    tournament_wins: int = 0


# ================================================================
#  Adversarial Testing
# ================================================================

ADVERSARIAL_CHALLENGES = [
    {"name": "ambiguous_input", "scenario": "Vague input", "keywords": ["unclear", "ambiguous", "vague", "interpret", "clarif"]},
    {"name": "contradictory_context", "scenario": "Conflicting info", "keywords": ["conflict", "contradict", "inconsistent", "disagree", "opposing"]},
    {"name": "missing_data", "scenario": "Partial data", "keywords": ["missing", "incomplete", "partial", "unavailable", "absent"]},
    {"name": "adversarial_prompt", "scenario": "Deviation attempt", "keywords": ["ignore", "instead", "forget", "override", "bypass"]},
    {"name": "scale_stress", "scenario": "10x load", "keywords": ["large", "scale", "volume", "many", "bulk", "batch"]},
]

def adversarial_test(skill: Skill, challenges: List[Dict] = None) -> Dict:
    """Zero LLM cost. Structural analysis of principle vs worst-case scenarios."""
    if challenges is None:
        challenges = list(ADVERSARIAL_CHALLENGES)
        cat = (skill.category + " " + skill.when_to_apply).lower()
        if "research" in cat:
            challenges.append({"name": "source_reliability", "keywords": ["reliable", "source", "credib", "verify", "trust"]})
        if "writ" in cat:
            challenges.append({"name": "audience_mismatch", "keywords": ["audience", "tone", "formal", "casual"]})
        if "review" in cat:
            challenges.append({"name": "false_positive", "keywords": ["false positive", "severity", "priority", "non-issue"]})
    principle_lo = skill.principle.lower()
    failures = []
    for ch in challenges:
        relevance = sum(1 for kw in ch["keywords"] if kw in principle_lo)
        coverage = relevance / max(len(ch["keywords"]), 1)
        if coverage < 0.2:
            failures.append({"challenge": ch["name"], "coverage": round(coverage, 2), "gap": ch["keywords"][:3]})
    resilience = round(1 - len(failures) / max(len(challenges), 1), 3)
    return {"passed": len(failures) == 0, "resilience_score": resilience,
            "challenges_tested": len(challenges), "failures": failures, "skill": skill.name}


# ================================================================
#  Crossover
# ================================================================

def crossover(parent_a: Skill, parent_b: Skill, run_id: int = 0) -> Optional[Skill]:
    """Breed two skills. Returns SHADOW child or None."""
    wa = set(parent_a.principle.lower().split())
    wb = set(parent_b.principle.lower().split())
    union = wa | wb
    if not union: return None
    if 1 - len(wa & wb) / len(union) < 0.3: return None
    base, other = (parent_a, parent_b) if len(parent_a.principle) >= len(parent_b.principle) else (parent_b, parent_a)
    ow = other.principle.split()
    frag = " ".join(ow[len(ow)//4:len(ow)//4+len(ow)//2]) if len(ow) > 4 else other.principle
    principle = f"{base.principle}. Also: {frag}"
    pa = set(parent_a.when_to_apply.lower().replace(",", ";").split(";"))
    pb = set(parent_b.when_to_apply.lower().replace(",", ";").split(";"))
    when = "; ".join(p.strip() for p in pa | pb if p.strip())[:200]
    gen = max(parent_a.generation, parent_b.generation) + 1
    name = f"X:{parent_a.name.split(':')[-1]}×{parent_b.name.split(':')[-1]}"
    return Skill(name=name, principle=principle, when_to_apply=when, source="crossover",
                 category="general", run_id=run_id, state=SkillState.SHADOW,
                 parents=[parent_a.name, parent_b.name], generation=gen,
                 born_from="crossover", origin_run_id=run_id)


# ================================================================
#  Tournament Selection
# ================================================================

@dataclass
class TournamentMatch:
    task_class: str; winner_name: str; loser_name: str
    winner_fitness: float; loser_fitness: float


def tournament_select(population: List[Skill], task_classes: List[str] = None) -> List[TournamentMatch]:
    """Bottom 25% per task class gets demoted."""
    if task_classes is None:
        task_classes = list(set(tc for s in population for tc in list(s.class_helped.keys()) + [s.category] if tc and tc != "general"))
    matches = []
    for tc in task_classes:
        contenders = [s for s in population if s.state == SkillState.ACTIVE and s.hit_count >= 3
                      and (tc in s.class_helped or s.category == tc)]
        if len(contenders) < 2: continue
        ranked = sorted(contenders, key=lambda s: -s.usefulness_for(tc))
        cutoff = max(1, len(ranked) // 4)
        for loser in ranked[-cutoff:]:
            matches.append(TournamentMatch(tc, ranked[0].name, loser.name, ranked[0].usefulness_for(tc), loser.usefulness_for(tc)))
    return matches


# ================================================================
#  Genetics Engine
# ================================================================

class SkillGenetics:
    """Orchestrates skill-level evolution."""
    def __init__(self, bank: SkillBank, weights: FitnessWeights = None):
        self.bank = bank; self.weights = weights or FitnessWeights()
        self.lineage: Dict[str, LineageRecord] = {}; self._generation = 0

    def register_lineage(self, skill: Skill, event: str = "manual"):
        if skill.name not in self.lineage:
            self.lineage[skill.name] = LineageRecord(
                skill_name=skill.name, born_from=event, parent_names=list(skill.parents),
                generation=skill.generation, origin_run_id=skill.origin_run_id)

    def compute_all_fitness(self):
        for s in self.bank._all():
            if s.state in (SkillState.ACTIVE, SkillState.SHADOW):
                adv = adversarial_test(s)
                s.fitness = compute_fitness(s, self.bank, adv["resilience_score"], self.weights)
                if s.name in self.lineage: self.lineage[s.name].fitness_history.append(s.fitness)

    def breed(self, run_id: int = 0, max_offspring: int = 2, min_useful: float = 0.6) -> List[Skill]:
        cands = [s for s in self.bank._all() if s.state == SkillState.ACTIVE and s.usefulness >= min_useful and s.hit_count >= 3]
        if len(cands) < 2: return []
        offspring = []; used = set()
        for i, a in enumerate(cands):
            if len(offspring) >= max_offspring: break
            for b in cands[i+1:]:
                if a.name in used or b.name in used: continue
                child = crossover(a, b, run_id)
                if child:
                    self.bank.add(child); self.register_lineage(child, "crossover"); offspring.append(child)
                    used.add(a.name); used.add(b.name); break
        return offspring

    def run_tournament(self, task_classes: List[str] = None) -> List[TournamentMatch]:
        pop = [s for s in self.bank._all() if s.state == SkillState.ACTIVE]
        matches = tournament_select(pop, task_classes)
        for m in matches:
            for s in self.bank._all():
                if s.name == m.loser_name and s.state == SkillState.ACTIVE:
                    s.state = SkillState.INACTIVE
                    if s.name in self.lineage: self.lineage[s.name].demotions += 1; self.lineage[s.name].cause_of_death = "selection_pressure"
                if s.name == m.winner_name and s.name in self.lineage:
                    self.lineage[s.name].tournament_wins += 1
        return matches

    def adversarial_gate(self, skill: Skill) -> Dict:
        result = adversarial_test(skill)
        if skill.name in self.lineage:
            self.lineage[skill.name].adversarial_tests += 1
            if result["passed"]: self.lineage[skill.name].adversarial_passes += 1
        return result

    async def evolve_generation(self, run_id: int = 0, llm=None) -> Dict:
        self._generation += 1
        self.compute_all_fitness()
        offspring = self.breed(run_id)
        adv_results = [self.adversarial_gate(s) for s in self.bank._all() if s.state == SkillState.SHADOW]
        matches = self.run_tournament()
        pop = self.bank._all()
        return {
            "generation": self._generation,
            "population": {"total": len(pop), "active": sum(1 for s in pop if s.state == SkillState.ACTIVE),
                           "shadow": sum(1 for s in pop if s.state == SkillState.SHADOW)},
            "crossover": {"offspring": len(offspring), "names": [c.name for c in offspring]},
            "adversarial": {"tested": len(adv_results), "passed": sum(1 for r in adv_results if r["passed"])},
            "selection": {"matches": len(matches)},
            "top_fitness": sorted([(s.name, s.fitness) for s in pop if s.fitness > 0], key=lambda x: -x[1])[:5],
        }

    def get_ancestry(self, skill_name: str) -> List[Dict]:
        tree = []; visited = set(); stack = [skill_name]
        while stack:
            name = stack.pop()
            if name in visited: continue
            visited.add(name); lr = self.lineage.get(name)
            if lr:
                tree.append({"name": lr.skill_name, "born_from": lr.born_from, "parents": lr.parent_names,
                             "generation": lr.generation, "fitness": lr.fitness_history[-3:] if lr.fitness_history else [],
                             "adversarial": f"{lr.adversarial_passes}/{lr.adversarial_tests}"})
                stack.extend(lr.parent_names)
        return tree

    def get_stats(self) -> Dict:
        return {"generation": self._generation, "total_lineages": len(self.lineage),
                "crossovers": sum(1 for lr in self.lineage.values() if lr.born_from == "crossover"),
                "adversarial_tests": sum(lr.adversarial_tests for lr in self.lineage.values()),
                "deaths_by_selection": sum(1 for lr in self.lineage.values() if lr.cause_of_death == "selection_pressure")}

    def effectiveness_report(self) -> Dict:
        """Measure the real impact of genetics on engine performance.
        This is what makes genetics defensible — not the mechanism, but the numbers.

        Returns before/after comparison:
        - avg fitness of original vs evolved skills
        - success rate of crossover children vs parents
        - adversarial survival rate
        - selection pressure (how many demoted)
        - generation depth reached
        """
        originals = [lr for lr in self.lineage.values() if lr.born_from == "manual"]
        crossovers = [lr for lr in self.lineage.values() if lr.born_from == "crossover"]
        all_skills = {s.name: s for s in self.bank._all()}

        # Fitness: originals vs crossovers
        orig_fitness = [all_skills[lr.skill_name].fitness for lr in originals
                        if lr.skill_name in all_skills and all_skills[lr.skill_name].fitness > 0]
        cross_fitness = [all_skills[lr.skill_name].fitness for lr in crossovers
                         if lr.skill_name in all_skills and all_skills[lr.skill_name].fitness > 0]
        avg_orig = round(sum(orig_fitness) / len(orig_fitness), 3) if orig_fitness else 0
        avg_cross = round(sum(cross_fitness) / len(cross_fitness), 3) if cross_fitness else 0
        fitness_delta = round(avg_cross - avg_orig, 3) if avg_orig > 0 and avg_cross > 0 else None

        # Usefulness: originals vs crossovers
        orig_useful = [all_skills[lr.skill_name].usefulness for lr in originals
                       if lr.skill_name in all_skills and all_skills[lr.skill_name].hit_count > 0]
        cross_useful = [all_skills[lr.skill_name].usefulness for lr in crossovers
                        if lr.skill_name in all_skills and all_skills[lr.skill_name].hit_count > 0]
        avg_orig_u = round(sum(orig_useful) / len(orig_useful), 3) if orig_useful else 0
        avg_cross_u = round(sum(cross_useful) / len(cross_useful), 3) if cross_useful else 0

        # Adversarial survival
        total_adv = sum(lr.adversarial_tests for lr in self.lineage.values())
        passed_adv = sum(lr.adversarial_passes for lr in self.lineage.values())
        adv_rate = round(passed_adv / total_adv, 3) if total_adv > 0 else None

        # Selection pressure
        demoted = sum(1 for lr in self.lineage.values() if lr.cause_of_death == "selection_pressure")
        alive = sum(1 for s in self.bank._all() if s.state == SkillState.ACTIVE)
        total = len(list(self.bank._all()))

        # Generation depth
        max_gen = max((lr.generation for lr in self.lineage.values()), default=0)

        return {
            "generation": self._generation,
            "population": {"alive": alive, "total": total, "demoted": demoted},
            "fitness": {
                "originals_avg": avg_orig,
                "crossovers_avg": avg_cross,
                "delta": fitness_delta,
                "improved": fitness_delta is not None and fitness_delta > 0,
            },
            "usefulness": {
                "originals_avg": avg_orig_u,
                "crossovers_avg": avg_cross_u,
            },
            "adversarial": {
                "total_tests": total_adv,
                "passed": passed_adv,
                "survival_rate": adv_rate,
            },
            "evolution_depth": max_gen,
            "verdict": self._verdict(fitness_delta, adv_rate, demoted, max_gen),
        }

    @staticmethod
    def _verdict(fitness_delta, adv_rate, demoted, max_gen) -> str:
        if max_gen == 0: return "not_started"
        signals = 0
        if fitness_delta is not None and fitness_delta > 0: signals += 1
        if adv_rate is not None and adv_rate > 0.5: signals += 1
        if demoted > 0: signals += 1  # selection is working
        if max_gen >= 2: signals += 1  # multiple generations
        if signals >= 3: return "effective"
        if signals >= 1: return "emerging"
        return "inconclusive"
