"""Tests for packs.py — PackMetadata, PackManager."""
import json
import os
import pytest
from agent_swarm.packs import PackMetadata, PackManager
from agent_swarm.skills import SkillBank


# ── PackMetadata ──

def test_pack_metadata_from_dict():
    data = {
        "name": "test-pack",
        "version": "2.0.0",
        "description": "A test pack",
        "author": "test",
        "category": "research",
        "tags": ["test", "research"],
        "skills": [
            {"name": "verify", "principle": "Always verify", "when_to_apply": "review"},
        ],
    }
    meta = PackMetadata.from_dict(data)
    assert meta.name == "test-pack"
    assert meta.version == "2.0.0"
    assert meta.category == "research"
    assert len(meta.skills) == 1


def test_pack_metadata_defaults():
    meta = PackMetadata.from_dict({"name": "minimal"})
    assert meta.version == "1.0.0"
    assert meta.skills == []
    assert meta.tags == []
    assert meta.category == "general"


def test_pack_metadata_to_skills():
    meta = PackMetadata.from_dict({
        "name": "test",
        "skills": [
            {"name": "s1", "principle": "P1", "when_to_apply": "W1"},
            {"name": "s2", "principle": "P2", "when_to_apply": "W2", "category": "writing"},
        ],
    })
    skills = meta.to_skills()
    assert len(skills) == 2
    assert skills[0].name == "s1"
    assert skills[0].source == "pack:test"
    assert skills[1].category == "writing"


def test_pack_metadata_to_skills_with_manifest():
    meta = PackMetadata.from_dict({
        "name": "test",
        "skills": [{
            "name": "s1", "principle": "P1", "when_to_apply": "W1",
            "manifest": {
                "capabilities": ["analyze"],
                "task_types": ["research"],
                "domain": "science",
            },
        }],
    })
    skills = meta.to_skills()
    assert skills[0].manifest is not None
    assert "analyze" in skills[0].manifest.capabilities


def test_pack_metadata_to_ontology_bundle():
    meta = PackMetadata.from_dict({
        "name": "test",
        "ontology_terms": [
            {"id": "Research", "label": "Research", "definition": "Investigation for new knowledge"},
        ],
        "ontology_relations": [
            {"predicate": "requires", "subject": "Research", "object": "Analysis"},
        ],
    })
    bundle = meta.to_ontology_bundle()
    assert bundle is not None
    assert bundle.bundle_id == "pack-test"
    assert len(bundle.terms) == 1
    assert len(bundle.relations) == 1


def test_pack_metadata_no_ontology():
    meta = PackMetadata.from_dict({"name": "test"})
    assert meta.to_ontology_bundle() is None


# ── PackManager ──

def test_pack_manager_init(tmp_path):
    pm = PackManager(packs_dir=str(tmp_path / "packs"))
    installed = pm.list_installed()
    assert isinstance(installed, list)


def test_pack_manager_install_from_path(tmp_path):
    # Create a pack directory
    pack_dir = tmp_path / "my-pack"
    pack_dir.mkdir()
    (pack_dir / "pack.json").write_text(json.dumps({
        "name": "my-pack",
        "version": "1.0.0",
        "skills": [{"name": "s1", "principle": "P", "when_to_apply": "W"}],
    }))

    user_dir = tmp_path / "user-packs"
    pm = PackManager(packs_dir=str(user_dir))
    result = pm.install_from_path(str(pack_dir))
    assert result is True
    assert pm.get("my-pack") is not None


def test_pack_manager_apply(tmp_path):
    pack_dir = tmp_path / "my-pack"
    pack_dir.mkdir()
    (pack_dir / "pack.json").write_text(json.dumps({
        "name": "my-pack",
        "skills": [
            {"name": "s1", "principle": "P1", "when_to_apply": "W1"},
            {"name": "s2", "principle": "P2", "when_to_apply": "W2"},
        ],
    }))

    user_dir = tmp_path / "user-packs"
    pm = PackManager(packs_dir=str(user_dir))
    pm.install_from_path(str(pack_dir))

    bank, bundles = pm.apply()
    assert isinstance(bank, SkillBank)
    all_skills = list(bank._all())
    names = [s.name for s in all_skills]
    assert "s1" in names
    assert "s2" in names


def test_pack_manager_uninstall(tmp_path):
    pack_dir = tmp_path / "my-pack"
    pack_dir.mkdir()
    (pack_dir / "pack.json").write_text(json.dumps({"name": "my-pack"}))

    user_dir = tmp_path / "user-packs"
    pm = PackManager(packs_dir=str(user_dir))
    pm.install_from_path(str(pack_dir))
    assert pm.uninstall("my-pack") is True
    assert pm.get("my-pack") is None


def test_pack_manager_install_nonexistent():
    pm = PackManager(packs_dir="/nonexistent/path")
    assert pm.install("nonexistent-pack") is False
