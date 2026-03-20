"""Tests for telemetry and skill preamble modules."""
import os
import tempfile
import threading
import time

import pytest

from agent_swarm.telemetry import TelemetryEvent, TelemetryWriter, TelemetryReader
from agent_swarm.skills import SkillPreamble


# ── TelemetryEvent ──


class TestTelemetryEvent:
    def test_timestamp_auto_set(self):
        before = time.time()
        ev = TelemetryEvent(event_type="test")
        after = time.time()
        assert before <= ev.timestamp <= after

    def test_explicit_timestamp_preserved(self):
        ev = TelemetryEvent(event_type="test", timestamp=123.0)
        assert ev.timestamp == 123.0

    def test_default_data(self):
        ev = TelemetryEvent(event_type="x")
        assert ev.data == {}


# ── TelemetryWriter ──


class TestTelemetryWriter:
    def test_emit_writes_to_file(self, tmp_path):
        path = str(tmp_path / "events.jsonl")
        w = TelemetryWriter(path)
        ev = w.emit("task_completed", {"task_id": "t1"})
        assert ev.event_type == "task_completed"
        assert os.path.exists(path)
        with open(path) as f:
            lines = f.readlines()
        assert len(lines) == 1
        assert '"task_completed"' in lines[0]

    def test_emit_event_writes_prebuilt(self, tmp_path):
        path = str(tmp_path / "events.jsonl")
        w = TelemetryWriter(path)
        ev = TelemetryEvent(event_type="custom", data={"k": "v"})
        w.emit_event(ev)
        r = TelemetryReader(path)
        events = r.read_all()
        assert len(events) == 1
        assert events[0].event_type == "custom"
        assert events[0].data == {"k": "v"}

    def test_path_property(self, tmp_path):
        path = str(tmp_path / "events.jsonl")
        w = TelemetryWriter(path)
        assert w.path == path

    def test_thread_safety(self, tmp_path):
        path = str(tmp_path / "events.jsonl")
        w = TelemetryWriter(path)
        n = 50
        threads = []
        for i in range(n):
            t = threading.Thread(target=w.emit, args=(f"evt_{i}",))
            threads.append(t)
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        r = TelemetryReader(path)
        events = r.read_all()
        assert len(events) == n

    def test_creates_parent_dirs(self, tmp_path):
        path = str(tmp_path / "sub" / "dir" / "events.jsonl")
        w = TelemetryWriter(path)
        w.emit("test")
        assert os.path.exists(path)


# ── TelemetryReader ──


class TestTelemetryReader:
    def test_read_all_empty_file(self, tmp_path):
        path = str(tmp_path / "empty.jsonl")
        r = TelemetryReader(path)
        assert r.read_all() == []

    def test_read_all(self, tmp_path):
        path = str(tmp_path / "events.jsonl")
        w = TelemetryWriter(path)
        w.emit("a", {"x": 1})
        w.emit("b", {"y": 2})
        r = TelemetryReader(path)
        events = r.read_all()
        assert len(events) == 2
        assert events[0].event_type == "a"
        assert events[1].event_type == "b"

    def test_filter_by_type(self, tmp_path):
        path = str(tmp_path / "events.jsonl")
        w = TelemetryWriter(path)
        w.emit("a")
        w.emit("b")
        w.emit("a")
        r = TelemetryReader(path)
        filtered = r.filter_by_type("a")
        assert len(filtered) == 2
        assert all(e.event_type == "a" for e in filtered)

    def test_count_by_type(self, tmp_path):
        path = str(tmp_path / "events.jsonl")
        w = TelemetryWriter(path)
        w.emit("x")
        w.emit("y")
        w.emit("x")
        w.emit("x")
        r = TelemetryReader(path)
        counts = r.count_by_type()
        assert counts == {"x": 3, "y": 1}

    def test_aggregate_stats(self, tmp_path):
        path = str(tmp_path / "events.jsonl")
        w = TelemetryWriter(path)
        w.emit("a")
        w.emit("b")
        r = TelemetryReader(path)
        stats = r.aggregate_stats()
        assert stats["total_events"] == 2
        assert stats["event_types"] == {"a": 1, "b": 1}
        assert stats["time_range_s"] >= 0
        assert stats["first_event"] > 0
        assert stats["last_event"] >= stats["first_event"]

    def test_aggregate_stats_empty(self, tmp_path):
        path = str(tmp_path / "empty.jsonl")
        r = TelemetryReader(path)
        stats = r.aggregate_stats()
        assert stats == {"total_events": 0, "event_types": {}, "time_range_s": 0}

    def test_handles_corrupt_lines(self, tmp_path):
        path = str(tmp_path / "events.jsonl")
        with open(path, "w") as f:
            f.write('{"event_type":"ok","data":{},"timestamp":1.0}\n')
            f.write("NOT JSON\n")
            f.write('{"event_type":"ok2","data":{},"timestamp":2.0}\n')
        r = TelemetryReader(path)
        events = r.read_all()
        assert len(events) == 2


# ── SkillPreamble ──


class TestSkillPreamble:
    def test_format_all_fields(self):
        p = SkillPreamble(session_id="s1", run_id="r1", config={"k": "v"})
        result = p.format_preamble()
        assert "[Session: s1]" in result
        assert "[Run: r1]" in result
        assert "[Config: k=v]" in result

    def test_format_empty(self):
        p = SkillPreamble()
        assert p.format_preamble() == ""

    def test_format_partial(self):
        p = SkillPreamble(session_id="s1")
        result = p.format_preamble()
        assert "[Session: s1]" in result
        assert "[Run:" not in result

    def test_notify_hooks(self):
        captured = []
        def hook(event, data):
            captured.append((event, data))
        p = SkillPreamble(analytics_hooks=[hook])
        p.notify_hooks("test_event", {"key": "val"})
        assert len(captured) == 1
        assert captured[0] == ("test_event", {"key": "val"})

    def test_notify_hooks_error_suppressed(self):
        def bad_hook(event, data):
            raise RuntimeError("boom")
        p = SkillPreamble(analytics_hooks=[bad_hook])
        # Should not raise
        p.notify_hooks("event")

    def test_notify_hooks_default_data(self):
        captured = []
        def hook(event, data):
            captured.append(data)
        p = SkillPreamble(analytics_hooks=[hook])
        p.notify_hooks("evt")
        assert captured[0] == {}
