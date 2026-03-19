"""Tests for memory.py — Memory, MemoryStore."""
import json
import os
import pytest
from agent_swarm.memory import Memory, MemoryStore


# ── Memory dataclass ──

def test_memory_creation():
    m = Memory(id="m1", type="long", content="test fact")
    assert m.id == "m1"
    assert m.type == "long"
    assert m.content == "test fact"
    assert m.access_count == 0
    assert m.timestamp > 0


def test_memory_to_dict():
    m = Memory(id="m1", type="short", content="hello", tags=["a", "b"])
    d = m.to_dict()
    assert d["id"] == "m1"
    assert d["tags"] == ["a", "b"]


def test_memory_from_dict():
    d = {"id": "m1", "type": "long", "content": "fact", "tags": ["x"], "access_count": 3}
    m = Memory.from_dict(d)
    assert m.id == "m1"
    assert m.access_count == 3
    assert m.tags == ["x"]


def test_memory_roundtrip():
    original = Memory(id="m1", type="entity", content="CompanyX", entity="CompanyX", tags=["ai"])
    d = original.to_dict()
    restored = Memory.from_dict(d)
    assert restored.id == original.id
    assert restored.entity == original.entity
    assert restored.tags == original.tags


def test_memory_from_dict_ignores_extra_keys():
    d = {"id": "m1", "type": "short", "content": "x", "unknown_field": 123}
    m = Memory.from_dict(d)
    assert m.id == "m1"


# ── MemoryStore: add / search / delete ──

def test_store_add(tmp_path):
    store = MemoryStore(str(tmp_path / "mem"), max_memories=100)
    m = store.add("long", "Python is great", tags=["lang"])
    assert m.id == "mem_1"
    assert m.type == "long"
    assert len(store.all()) == 1


def test_store_add_increments_id(tmp_path):
    store = MemoryStore(str(tmp_path / "mem"), max_memories=100)
    m1 = store.add("short", "a")
    m2 = store.add("short", "b")
    assert m1.id == "mem_1"
    assert m2.id == "mem_2"


def test_store_search_keyword(tmp_path):
    store = MemoryStore(str(tmp_path / "mem"), max_memories=100)
    store.add("long", "Python backend development")
    store.add("long", "React frontend framework")
    results = store.search("Python backend")
    assert len(results) >= 1
    assert "Python" in results[0].content


def test_store_search_by_type(tmp_path):
    store = MemoryStore(str(tmp_path / "mem"), max_memories=100)
    store.add("short", "temp note", run_id=1)
    store.add("long", "permanent fact")
    results = store.search("note", type="short")
    assert all(r.type == "short" for r in results)


def test_store_search_no_match(tmp_path):
    store = MemoryStore(str(tmp_path / "mem"), max_memories=100)
    store.add("long", "Python backend")
    results = store.search("quantum physics")
    assert len(results) == 0


def test_store_search_relevance_ranking(tmp_path):
    store = MemoryStore(str(tmp_path / "mem"), max_memories=100)
    store.add("short", "weather today is sunny")
    store.add("long", "Python data analysis machine learning")
    results = store.search("Python data analysis")
    assert len(results) >= 1
    # Long-term gets boost, plus more keyword overlap
    assert "Python" in results[0].content


def test_store_search_updates_access_count(tmp_path):
    store = MemoryStore(str(tmp_path / "mem"), max_memories=100)
    m = store.add("long", "important fact")
    store.search("important fact")
    # Refetch from store
    assert store.all()[0].access_count == 1


def test_store_delete(tmp_path):
    store = MemoryStore(str(tmp_path / "mem"), max_memories=100)
    m = store.add("long", "to delete")
    assert store.delete(m.id) is True
    assert len(store.all()) == 0


def test_store_delete_nonexistent(tmp_path):
    store = MemoryStore(str(tmp_path / "mem"), max_memories=100)
    assert store.delete("nonexistent") is False


# ── Eviction ──

def test_store_eviction_short_first(tmp_path):
    store = MemoryStore(str(tmp_path / "mem"), max_memories=3)
    store.add("long", "keep me")
    store.add("short", "evict me", run_id=1)
    store.add("long", "also keep")
    # This add should trigger eviction
    store.add("long", "fourth")
    assert len(store.all()) == 3
    contents = [m.content for m in store.all()]
    assert "evict me" not in contents


# ── clear_short_term ──

def test_clear_short_term_all(tmp_path):
    store = MemoryStore(str(tmp_path / "mem"), max_memories=100)
    store.add("short", "temp1", run_id=1)
    store.add("short", "temp2", run_id=2)
    store.add("long", "permanent")
    store.clear_short_term()
    assert len(store.all()) == 1
    assert store.all()[0].type == "long"


def test_clear_short_term_by_run(tmp_path):
    store = MemoryStore(str(tmp_path / "mem"), max_memories=100)
    store.add("short", "run1", run_id=1)
    store.add("short", "run2", run_id=2)
    store.clear_short_term(run_id=1)
    remaining = store.all()
    assert len(remaining) == 1
    assert remaining[0].content == "run2"


# ── format_for_prompt ──

def test_format_for_prompt(tmp_path):
    store = MemoryStore(str(tmp_path / "mem"), max_memories=100)
    store.add("long", "Python is a programming language", tags=["lang"])
    result = store.format_for_prompt("Python")
    assert "[Agent Memory]" in result
    assert "Python" in result


def test_format_for_prompt_empty(tmp_path):
    store = MemoryStore(str(tmp_path / "mem"), max_memories=100)
    result = store.format_for_prompt("nonexistent query")
    assert result == ""


# ── File persistence ──

def test_persistence_save_load(tmp_path):
    path = str(tmp_path / "mem")
    store1 = MemoryStore(path, max_memories=100)
    store1.add("long", "persistent data", tags=["test"])

    store2 = MemoryStore(path, max_memories=100)
    assert len(store2.all()) == 1
    assert store2.all()[0].content == "persistent data"


# ── get_entity / get_context ──

def test_get_entity(tmp_path):
    store = MemoryStore(str(tmp_path / "mem"), max_memories=100)
    store.add("entity", "AI startup", entity="CompanyX")
    store.add("entity", "Founded 2020", entity="CompanyX")
    store.add("entity", "Different co", entity="CompanyY")
    results = store.get_entity("companyx")
    assert len(results) == 2


def test_get_context(tmp_path):
    store = MemoryStore(str(tmp_path / "mem"), max_memories=100)
    store.add("context", "Use careful indentation", skill="YAMLParser")
    store.add("context", "Validate schema first", skill="YAMLParser")
    results = store.get_context("yamlparser")
    assert len(results) == 2


# ── stats ──

def test_stats(tmp_path):
    store = MemoryStore(str(tmp_path / "mem"), max_memories=100)
    store.add("long", "fact1")
    store.add("short", "temp", run_id=1)
    store.add("entity", "co", entity="X")
    s = store.stats()
    assert s["total"] == 3
    assert s["by_type"]["long"] == 1
    assert s["entities"] == 1
