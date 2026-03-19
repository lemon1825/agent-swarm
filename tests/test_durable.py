"""Tests for durable.py — DurableCheckpoint persistence."""
import json
import os
import time
import pytest
from agent_swarm.durable import DurableCheckpoint


# ── Save and load ──

def test_save_and_load(tmp_path):
    dc = DurableCheckpoint(str(tmp_path))
    dc.save("run1", {"completed": {"t1": True}, "llm_calls": 5})
    loaded = dc.load("run1")
    assert loaded is not None
    assert loaded["completed"]["t1"] is True
    assert loaded["llm_calls"] == 5
    assert loaded["_durable_run_id"] == "run1"
    assert loaded["_durable_saved_at"] > 0


def test_load_nonexistent(tmp_path):
    dc = DurableCheckpoint(str(tmp_path))
    assert dc.load("nonexistent") is None


def test_save_overwrites(tmp_path):
    dc = DurableCheckpoint(str(tmp_path))
    dc.save("run1", {"state": "v1"})
    dc.save("run1", {"state": "v2"})
    loaded = dc.load("run1")
    assert loaded["state"] == "v2"


# ── Delete ──

def test_delete(tmp_path):
    dc = DurableCheckpoint(str(tmp_path))
    dc.save("run1", {"data": 1})
    assert dc.delete("run1") is True
    assert dc.load("run1") is None


def test_delete_nonexistent(tmp_path):
    dc = DurableCheckpoint(str(tmp_path))
    assert dc.delete("nonexistent") is False


# ── List ──

def test_list(tmp_path):
    dc = DurableCheckpoint(str(tmp_path))
    dc.save("run1", {"completed": {"t1": True}})
    dc.save("run2", {"completed": {"t1": True, "t2": True}})
    results = dc.list()
    assert len(results) == 2
    ids = {r["run_id"] for r in results}
    assert "run1" in ids
    assert "run2" in ids


def test_list_empty(tmp_path):
    dc = DurableCheckpoint(str(tmp_path))
    assert dc.list() == []


# ── Run ID sanitization ──

def test_sanitized_filename(tmp_path):
    dc = DurableCheckpoint(str(tmp_path))
    dc.save("run/with:special<chars>", {"data": 1})
    # Should create a file with sanitized name
    files = [f for f in os.listdir(str(tmp_path)) if f.endswith(".json")]
    assert len(files) == 1
    assert "/" not in files[0]
    assert ":" not in files[0]


# ── Atomic write (tmp + replace) ──

def test_atomic_write_no_tmp_left(tmp_path):
    dc = DurableCheckpoint(str(tmp_path))
    dc.save("run1", {"data": 1})
    files = os.listdir(str(tmp_path))
    tmp_files = [f for f in files if f.endswith(".tmp")]
    assert len(tmp_files) == 0


# ── Cleanup by age ──

def test_cleanup_by_age(tmp_path):
    dc = DurableCheckpoint(str(tmp_path))
    # Save with old timestamp
    dc.save("old_run", {"completed": {}})
    # Manually backdate the saved_at
    f = dc._file("old_run")
    with open(f) as fh:
        data = json.load(fh)
    data["_durable_saved_at"] = time.time() - 100 * 3600  # 100 hours ago
    with open(f, "w") as fh:
        json.dump(data, fh)

    dc.save("new_run", {"completed": {}})

    removed = dc.cleanup(max_age_hours=72)
    assert removed == 1
    assert dc.load("old_run") is None
    assert dc.load("new_run") is not None


# ── Corrupted file ──

def test_load_corrupted_returns_none(tmp_path):
    dc = DurableCheckpoint(str(tmp_path))
    # Write invalid JSON
    f = dc._file("bad")
    with open(f, "w") as fh:
        fh.write("not valid json{{{")
    assert dc.load("bad") is None


# ── create_hook ──

def test_create_hook_checkpoint_saved(tmp_path):
    dc = DurableCheckpoint(str(tmp_path))
    hook = dc.create_hook("run1")
    checkpoint_data = {"completed": {"t1": True}, "llm_calls": 3}
    hook("checkpoint_saved", {"checkpoint": checkpoint_data})
    loaded = dc.load("run1")
    assert loaded is not None
    assert loaded["completed"]["t1"] is True


def test_create_hook_run_completed(tmp_path):
    dc = DurableCheckpoint(str(tmp_path))
    hook = dc.create_hook("run1")
    data = {"checkpoint": {"completed": {"t1": True}}, "final_output": "done"}
    hook("run_completed", data)
    assert dc.load("run1") is not None
    assert dc.load("run1_final") is not None


def test_create_hook_ignores_other_events(tmp_path):
    dc = DurableCheckpoint(str(tmp_path))
    hook = dc.create_hook("run1")
    hook("task_started", {"task_id": "t1"})
    assert dc.load("run1") is None
