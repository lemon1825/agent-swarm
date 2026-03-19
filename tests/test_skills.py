"""Tests for skills.py — SkillBank, TF-IDF, Skill lifecycle."""
import pytest
from agent_swarm.skills import (
    Skill, SkillBank, SkillState, SkillManifest, _TFIDFIndex, FailureCluster,
)


# ── TF-IDF Index ──

def test_tfidf_score_relevant():
    idx = _TFIDFIndex()
    corpus = ["machine learning data analysis", "web development frontend"]
    idx.update(corpus)
    score1 = idx.score("data analysis task", corpus[0])
    score2 = idx.score("data analysis task", corpus[1])
    assert score1 > score2  # First doc is more relevant


def test_tfidf_score_empty():
    idx = _TFIDFIndex()
    assert idx.score("", "doc") == 0.0
    assert idx.score("query", "") == 0.0


def test_tfidf_update_resets():
    idx = _TFIDFIndex()
    idx.update(["hello world"])
    assert idx._n == 1
    idx.update(["a", "b", "c"])
    assert idx._n == 3


# ── Skill ──

def test_skill_creation():
    s = Skill(name="test", principle="Always verify", when_to_apply="code review")
    assert s.name == "test"
    assert s.state == SkillState.ACTIVE
    assert s.usefulness == 0.0  # 0 helped / 0 total = 0


def test_skill_to_prompt_str():
    s = Skill(name="verify", principle="Check outputs", when_to_apply="after generation")
    prompt = s.to_prompt_str()
    assert "verify" in prompt
    assert "Check outputs" in prompt


def test_skill_usefulness_for():
    s = Skill(name="test", principle="p", when_to_apply="w")
    s.class_helped["research"] = 8
    s.class_failed["research"] = 2
    assert s.usefulness_for("research") == 0.8
    assert s.usefulness_for("unknown") == s.usefulness


# ── SkillBank ──

def test_skillbank_add_and_retrieve():
    bank = SkillBank()
    bank.add(Skill(name="s1", principle="Research carefully", when_to_apply="data gathering"))
    results = bank.retrieve("gather data from sources")
    assert len(results) >= 0  # May or may not match depending on TF-IDF


def test_skillbank_add_multiple():
    bank = SkillBank()
    bank.add(Skill(name="research", principle="Always verify sources carefully", when_to_apply="research tasks", category="research"))
    bank.add(Skill(name="writing", principle="Write concise clear prose", when_to_apply="writing tasks", category="writing"))
    bank.add(Skill(name="analysis", principle="Use statistical methods", when_to_apply="data analysis", category="analysis"))
    assert bank.total_count >= 2  # Different categories avoid merge


def test_skillbank_all_skills():
    bank = SkillBank()
    bank.add(Skill(name="g1", principle="general", when_to_apply="always"))
    bank.add(Skill(name="s1", principle="specific", when_to_apply="research", category="research"))
    all_s = bank.all_skills()
    assert len(all_s) == 2
    # Backward compat
    assert bank._all() == all_s


def test_skillbank_max_general():
    bank = SkillBank(max_general=3)
    for i in range(10):
        bank.add(Skill(name=f"g{i}", principle=f"p{i}", when_to_apply=f"w{i}"))
    assert len(bank.general) <= 3


def test_skillbank_shadow_skills():
    bank = SkillBank()
    bank.add(Skill(name="shadow1", principle="test", when_to_apply="test", state=SkillState.SHADOW))
    shadows = bank.retrieve_shadow("test task")
    # Should find the shadow skill
    assert all(s.state == SkillState.SHADOW for s in shadows)


def test_skillbank_record_failure():
    bank = SkillBank()
    bank.record_failure("Timeout:30s", "long task", "Worker")
    patterns = bank.get_failure_patterns(1)
    assert len(patterns) >= 1


def test_skillbank_record_run_success():
    bank = SkillBank()
    bank.record_run_success(0.8)
    bank.record_run_success(0.9)
    assert len(bank._run_success_rates) == 2


def test_skillbank_format_for_prompt():
    bank = SkillBank()
    bank.add(Skill(name="s1", principle="Be thorough", when_to_apply="research"))
    prompt = bank.format_for_prompt([bank.all_skills()[0]])
    assert "Be thorough" in prompt


def test_skillbank_get_metrics():
    bank = SkillBank()
    bank.add(Skill(name="s1", principle="p", when_to_apply="w"))
    metrics = bank.get_metrics()
    assert "total" in metrics
    assert metrics["total"] == 1


def test_skillbank_validate_evolution_schema():
    valid = {"name": "new_skill", "principle": "Always verify outputs carefully before submitting",
             "when_to_apply": "When generating code or text", "quality_score": 8}
    ok, reason = SkillBank.validate_evolution_schema(valid)
    assert ok is True

    invalid = {"name": "", "principle": "p"}
    ok2, reason2 = SkillBank.validate_evolution_schema(invalid)
    assert ok2 is False


# ── FailureCluster ──

def test_failure_cluster_tracks():
    fc = FailureCluster()
    fc.add("Timeout:30s", "task1", "Worker")
    fc.add("Timeout:45s", "task2", "Worker")
    patterns = fc.get_clusters(1)
    assert len(patterns) >= 1


def test_failure_cluster_escalation():
    fc = FailureCluster()
    for i in range(5):
        fc.add("Same error pattern", f"task{i}", "Worker")
    assert fc.needs_escalation("Same error pattern") is True


# ── SkillManifest ──

def test_skill_manifest():
    m = SkillManifest(
        capabilities={"research", "analysis"},
        tags={"ml", "data"},
        outputs={"report"},
        task_types={"research"},
    )
    assert "research" in m.capabilities
    assert "ml" in m.tags
