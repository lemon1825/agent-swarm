"""Tests for Blueprint Registry (NVIDIA AI Factory pattern)."""
import pytest
from agent_swarm.playbooks import (
    Blueprint, BlueprintMetadata, BlueprintRegistry, BlueprintValidator,
    BLUEPRINT_REGISTRY, SOPPlaybook, SOPStep, BUILTIN_PLAYBOOKS,
)


class TestBlueprintMetadata:
    def test_frozen(self):
        m = BlueprintMetadata(version="1.0.0")
        with pytest.raises(AttributeError):
            m.version = "2.0.0"

    def test_defaults(self):
        m = BlueprintMetadata()
        assert m.version == "1.0.0"
        assert m.validated is False
        assert m.tags == ()


class TestBlueprint:
    def test_frozen(self):
        pb = SOPPlaybook(name="test", description="desc")
        bp = Blueprint(playbook=pb)
        with pytest.raises(AttributeError):
            bp.playbook = None

    def test_name_property(self):
        pb = SOPPlaybook(name="my-bp", description="desc")
        bp = Blueprint(playbook=pb)
        assert bp.name == "my-bp"

    def test_is_validated(self):
        pb = SOPPlaybook(name="test", description="desc")
        bp1 = Blueprint(playbook=pb, metadata=BlueprintMetadata(validated=False))
        bp2 = Blueprint(playbook=pb, metadata=BlueprintMetadata(validated=True))
        assert bp1.is_validated is False
        assert bp2.is_validated is True


class TestBlueprintRegistry:
    def test_register_and_get(self):
        reg = BlueprintRegistry()
        pb = SOPPlaybook(name="test", description="desc")
        bp = Blueprint(playbook=pb, metadata=BlueprintMetadata(validated=True))
        reg.register("test", bp)
        assert reg.get("test") is bp
        assert reg.count == 1

    def test_get_nonexistent(self):
        reg = BlueprintRegistry()
        assert reg.get("nonexistent") is None

    def test_list_all(self):
        reg = BlueprintRegistry()
        pb1 = SOPPlaybook(name="a", description="")
        pb2 = SOPPlaybook(name="b", description="")
        reg.register("a", Blueprint(playbook=pb1))
        reg.register("b", Blueprint(playbook=pb2))
        assert len(reg.list_all()) == 2

    def test_list_validated(self):
        reg = BlueprintRegistry()
        pb1 = SOPPlaybook(name="valid", description="")
        pb2 = SOPPlaybook(name="draft", description="")
        reg.register("valid", Blueprint(playbook=pb1, metadata=BlueprintMetadata(validated=True)))
        reg.register("draft", Blueprint(playbook=pb2, metadata=BlueprintMetadata(validated=False)))
        validated = reg.list_validated()
        assert len(validated) == 1
        assert "valid" in validated

    def test_search_by_tag(self):
        reg = BlueprintRegistry()
        pb = SOPPlaybook(name="tagged", description="")
        reg.register("tagged", Blueprint(
            playbook=pb,
            metadata=BlueprintMetadata(tags=("review", "quality")),
        ))
        reg.register("other", Blueprint(
            playbook=SOPPlaybook(name="other", description=""),
            metadata=BlueprintMetadata(tags=("deploy",)),
        ))
        results = reg.search_by_tag("review")
        assert len(results) == 1
        assert results[0].name == "tagged"

    def test_from_playbook(self):
        reg = BlueprintRegistry()
        pb = SOPPlaybook(name="quick", description="fast workflow")
        bp = reg.from_playbook("quick", pb, version="2.0.0", validated=True, tags=("fast",))
        assert bp.metadata.version == "2.0.0"
        assert bp.is_validated is True
        assert reg.get("quick") is bp


class TestBlueprintValidator:
    def test_valid_blueprint(self):
        pb = SOPPlaybook(name="good", description="ok", steps=[
            SOPStep(name="A", role="Dev", description="do A"),
            SOPStep(name="B", role="QA", description="do B", depends_on=["A"]),
        ])
        bp = Blueprint(playbook=pb)
        passed, issues = BlueprintValidator.validate(bp)
        assert passed is True
        assert issues == []

    def test_empty_steps(self):
        pb = SOPPlaybook(name="empty", description="no steps")
        bp = Blueprint(playbook=pb)
        passed, issues = BlueprintValidator.validate(bp)
        assert passed is False
        assert "No steps" in issues[0]

    def test_missing_role(self):
        pb = SOPPlaybook(name="bad", description="x", steps=[
            SOPStep(name="A", role="", description="do A"),
        ])
        bp = Blueprint(playbook=pb)
        passed, issues = BlueprintValidator.validate(bp)
        assert passed is False
        assert any("missing role" in i for i in issues)

    def test_invalid_dependency(self):
        pb = SOPPlaybook(name="bad", description="x", steps=[
            SOPStep(name="A", role="Dev", description="do A", depends_on=["NONEXIST"]),
        ])
        bp = Blueprint(playbook=pb)
        passed, issues = BlueprintValidator.validate(bp)
        assert passed is False
        assert any("unknown step" in i for i in issues)

    def test_circular_dependency(self):
        pb = SOPPlaybook(name="cycle", description="x", steps=[
            SOPStep(name="A", role="Dev", description="do A", depends_on=["B"]),
            SOPStep(name="B", role="Dev", description="do B", depends_on=["A"]),
        ])
        bp = Blueprint(playbook=pb)
        passed, issues = BlueprintValidator.validate(bp)
        assert passed is False
        assert any("Circular" in i for i in issues)

    def test_validate_and_certify(self):
        reg = BlueprintRegistry()
        pb = SOPPlaybook(name="test", description="ok", steps=[
            SOPStep(name="A", role="Dev", description="do A"),
        ])
        reg.from_playbook("test", pb, validated=False)
        assert reg.get("test").is_validated is False
        passed, issues = BlueprintValidator.validate_and_certify(reg, "test")
        assert passed is True
        assert reg.get("test").is_validated is True
        assert "structural_check" in reg.get("test").metadata.test_results[0]

    def test_validate_all_builtins(self):
        """Every builtin playbook should pass structural validation."""
        for key in BUILTIN_PLAYBOOKS:
            bp = BLUEPRINT_REGISTRY.get(key)
            passed, issues = BlueprintValidator.validate(bp)
            assert passed is True, f"{key} failed: {issues}"


class TestBuiltinRegistry:
    def test_all_builtins_registered(self):
        for key in BUILTIN_PLAYBOOKS:
            bp = BLUEPRINT_REGISTRY.get(key)
            assert bp is not None, f"Missing blueprint: {key}"
            assert bp.is_validated is True

    def test_count(self):
        assert BLUEPRINT_REGISTRY.count == len(BUILTIN_PLAYBOOKS)

    def test_all_tagged_builtin(self):
        for key in BUILTIN_PLAYBOOKS:
            bp = BLUEPRINT_REGISTRY.get(key)
            assert "builtin" in bp.metadata.tags
