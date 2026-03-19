"""Tests for genetics.py — fitness, crossover, tournament, SkillGenetics."""
import pytest
from agent_swarm.skills import Skill, SkillBank, SkillState
from agent_swarm.genetics import (
    FitnessWeights, compute_fitness, LineageRecord,
    adversarial_test, crossover, tournament_select,
    TournamentMatch, SkillGenetics, ADVERSARIAL_CHALLENGES,
)


def _make_skill(name="test", principle="Always verify outputs carefully",
                when_to_apply="code review", hit_count=5, helped=4, failed=1,
                state=SkillState.ACTIVE, category="general"):
    s = Skill(name=name, principle=principle, when_to_apply=when_to_apply,
              source="test", category=category, state=state)
    s.hit_count = hit_count
    s.helped_count = helped
    s.failed_count = failed
    return s


def _make_bank(*skills):
    bank = SkillBank()
    for s in skills:
        bank.add(s)
    return bank


# ── FitnessWeights ──

def test_fitness_weights_defaults():
    w = FitnessWeights()
    total = (w.success_rate + w.retry_reduction + w.latency_bonus +
             w.validation_pass + w.task_class_fit + w.adversarial_robustness)
    assert abs(total - 1.0) < 0.01  # Weights should sum to 1.0


# ── compute_fitness ──

def test_compute_fitness_range():
    s = _make_skill()
    bank = _make_bank(s)
    fitness = compute_fitness(s, bank)
    assert 0.0 <= fitness <= 1.0


def test_compute_fitness_custom_weights():
    s = _make_skill()
    bank = _make_bank(s)
    w = FitnessWeights(success_rate=1.0, retry_reduction=0, latency_bonus=0,
                       validation_pass=0, task_class_fit=0, adversarial_robustness=0)
    fitness = compute_fitness(s, bank, weights=w)
    assert fitness == round(s.usefulness, 3)


def test_compute_fitness_zero_hit():
    s = _make_skill(hit_count=0, helped=0, failed=0)
    bank = _make_bank(s)
    fitness = compute_fitness(s, bank)
    assert 0.0 <= fitness <= 1.0


# ── LineageRecord ──

def test_lineage_record_defaults():
    lr = LineageRecord(skill_name="test")
    assert lr.born_from == "manual"
    assert lr.generation == 0
    assert lr.fitness_history == []
    assert lr.tournament_wins == 0


# ── adversarial_test ──

def test_adversarial_test_returns_dict():
    s = _make_skill()
    result = adversarial_test(s)
    assert "passed" in result
    assert "resilience_score" in result
    assert "challenges_tested" in result
    assert 0.0 <= result["resilience_score"] <= 1.0


def test_adversarial_test_custom_challenges():
    s = _make_skill(principle="handle missing data gracefully when data is incomplete or partial or absent or unavailable")
    challenges = [{"name": "missing_data", "keywords": ["missing", "incomplete", "partial", "unavailable", "absent"]}]
    result = adversarial_test(s, challenges)
    # All keywords covered → should pass
    assert result["resilience_score"] >= 0.8


# ── crossover ──

def test_crossover_produces_child():
    a = _make_skill(name="skill_a", principle="Always verify outputs before finalizing them to ensure accuracy")
    b = _make_skill(name="skill_b", principle="Consider edge cases thoroughly in testing phases for robustness")
    child = crossover(a, b, run_id=1)
    # May return None if diversity too low; check both cases
    if child is not None:
        assert child.state == SkillState.SHADOW
        assert child.generation > 0
        assert "X:" in child.name


def test_crossover_too_similar_returns_none():
    a = _make_skill(name="a", principle="verify outputs")
    b = _make_skill(name="b", principle="verify outputs")
    child = crossover(a, b)
    assert child is None


def test_crossover_empty_principle_returns_none():
    a = _make_skill(name="a", principle="")
    b = _make_skill(name="b", principle="")
    child = crossover(a, b)
    assert child is None


# ── tournament_select ──

def test_tournament_select_with_population():
    skills = []
    for i in range(6):
        s = _make_skill(name=f"s{i}", hit_count=5, helped=i, failed=5-i, category="research")
        s.class_helped = {"research": i}
        s.class_failed = {"research": 5-i}
        skills.append(s)
    matches = tournament_select(skills, task_classes=["research"])
    # Should produce matches (bottom 25% demoted)
    assert isinstance(matches, list)
    for m in matches:
        assert isinstance(m, TournamentMatch)


def test_tournament_select_too_few():
    s = _make_skill(name="lone", hit_count=5)
    s.class_helped = {"research": 3}
    matches = tournament_select([s], task_classes=["research"])
    assert matches == []


# ── SkillGenetics ──

def test_genetics_register_lineage():
    bank = _make_bank(_make_skill())
    gen = SkillGenetics(bank)
    skill = list(bank._all())[0]
    gen.register_lineage(skill, "manual")
    assert skill.name in gen.lineage


def test_genetics_compute_all_fitness():
    s = _make_skill()
    bank = _make_bank(s)
    gen = SkillGenetics(bank)
    gen.register_lineage(s)
    gen.compute_all_fitness()
    assert s.fitness > 0


def test_genetics_get_stats():
    bank = _make_bank(_make_skill())
    gen = SkillGenetics(bank)
    stats = gen.get_stats()
    assert stats["generation"] == 0
    assert "crossovers" in stats


def test_genetics_breed_needs_minimum():
    s = _make_skill(hit_count=1, helped=0)
    bank = _make_bank(s)
    gen = SkillGenetics(bank)
    offspring = gen.breed(run_id=1)
    assert offspring == []
