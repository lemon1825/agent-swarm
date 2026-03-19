"""Tests for session.py — SessionStore protocol, InMemorySessionStore."""
import pytest
from agent_swarm.session import SessionStore, InMemorySessionStore


def test_in_memory_implements_protocol():
    store = InMemorySessionStore()
    assert isinstance(store, SessionStore)


def test_load_new_session():
    store = InMemorySessionStore()
    data = store.load_session("new_id")
    assert "memory" in data
    assert "runs" in data
    assert "metadata" in data
    assert data["memory"] == []


def test_save_and_load():
    store = InMemorySessionStore()
    store.save_session("s1", {"memory": [{"item": 1}], "runs": ["r1"], "metadata": {"key": "val"}})
    data = store.load_session("s1")
    assert data["metadata"]["key"] == "val"
    assert len(data["runs"]) == 1


def test_append_memory():
    store = InMemorySessionStore()
    store.append_memory("s1", {"fact": "Python is great"})
    store.append_memory("s1", {"fact": "Tests are important"})
    data = store.load_session("s1")
    assert len(data["memory"]) == 2
    assert data["memory"][0]["fact"] == "Python is great"


def test_append_memory_to_existing():
    store = InMemorySessionStore()
    store.save_session("s1", {"memory": [{"old": True}], "runs": [], "metadata": {}})
    store.append_memory("s1", {"new": True})
    data = store.load_session("s1")
    assert len(data["memory"]) == 2
