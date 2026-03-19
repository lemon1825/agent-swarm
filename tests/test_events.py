"""Tests for events.py — Event, EventBus, global bus."""
import queue
import pytest
from agent_swarm.events import Event, EventBus, get_event_bus, set_event_bus


# ── Event dataclass ──

def test_event_creation():
    e = Event("task_start", {"task_id": "t1"})
    assert e.type == "task_start"
    assert e.data["task_id"] == "t1"
    assert e.timestamp > 0
    assert e.run_id == ""


def test_event_to_dict():
    e = Event("log", {"msg": "hello"}, run_id="run1")
    d = e.to_dict()
    assert d["type"] == "log"
    assert d["data"]["msg"] == "hello"
    assert d["run_id"] == "run1"
    assert "timestamp" in d


def test_event_to_json():
    e = Event("task_complete", {"task_id": "t1"})
    j = e.to_json()
    assert '"task_complete"' in j
    assert '"task_id"' in j


def test_event_default_data():
    e = Event("phase_change")
    assert e.data == {}


# ── EventBus: on / emit ──

def test_bus_on_and_emit():
    bus = EventBus()
    received = []
    bus.on("task_start", lambda e: received.append(e))
    bus.emit(Event("task_start", {"id": "t1"}))
    assert len(received) == 1
    assert received[0].data["id"] == "t1"


def test_bus_on_ignores_other_types():
    bus = EventBus()
    received = []
    bus.on("task_start", lambda e: received.append(e))
    bus.emit(Event("task_complete", {"id": "t1"}))
    assert len(received) == 0


def test_bus_on_all():
    bus = EventBus()
    received = []
    bus.on_all(lambda e: received.append(e))
    bus.emit(Event("task_start"))
    bus.emit(Event("task_complete"))
    assert len(received) == 2


def test_bus_multiple_listeners():
    bus = EventBus()
    a, b = [], []
    bus.on("x", lambda e: a.append(1))
    bus.on("x", lambda e: b.append(1))
    bus.emit(Event("x"))
    assert len(a) == 1
    assert len(b) == 1


# ── Listener error isolation ──

def test_bad_listener_does_not_crash():
    bus = EventBus()
    good = []
    bus.on("x", lambda e: (_ for _ in ()).throw(ValueError("boom")))
    bus.on("x", lambda e: good.append(1))
    bus.emit(Event("x"))
    # The good listener may or may not fire depending on order,
    # but emit() must not raise
    assert True  # If we got here, no crash


def test_bad_all_listener_does_not_crash():
    bus = EventBus()
    bus.on_all(lambda e: (_ for _ in ()).throw(ValueError("boom")))
    bus.emit(Event("x"))
    assert True


# ── History ──

def test_history():
    bus = EventBus()
    bus.emit(Event("a"))
    bus.emit(Event("b"))
    h = bus.history()
    assert len(h) == 2
    assert h[0].type == "a"
    assert h[1].type == "b"


def test_history_returns_copy():
    bus = EventBus()
    bus.emit(Event("a"))
    h = bus.history()
    h.clear()
    assert len(bus.history()) == 1


def test_history_max_capped():
    bus = EventBus()
    bus._max_history = 5
    for i in range(10):
        bus.emit(Event(f"e{i}"))
    assert len(bus.history()) == 5
    assert bus.history()[0].type == "e5"


# ── Clear ──

def test_clear():
    bus = EventBus()
    bus.emit(Event("a"))
    bus.emit(Event("b"))
    bus.clear()
    assert len(bus.history()) == 0


# ── Queue overflow ──

def test_queue_overflow_does_not_crash():
    bus = EventBus()
    bus._queue = queue.Queue(maxsize=2)
    for i in range(10):
        bus.emit(Event(f"e{i}"))
    # Should not raise; excess events are silently dropped
    assert len(bus.history()) == 10


# ── Convenience emitters ──

def test_run_start():
    bus = EventBus()
    received = []
    bus.on("run_start", lambda e: received.append(e))
    bus.run_start("r1", "Test mission", [{"id": "t1", "name": "Task 1", "role": "Researcher"}])
    assert len(received) == 1
    assert received[0].data["mission"] == "Test mission"
    assert received[0].run_id == "r1"


def test_phase_change():
    bus = EventBus()
    received = []
    bus.on("phase_change", lambda e: received.append(e))
    bus.phase_change("r1", "execution")
    assert received[0].data["phase"] == "execution"


def test_task_start_event():
    bus = EventBus()
    received = []
    bus.on("task_start", lambda e: received.append(e))
    bus.task_start("r1", "t1", "Researcher")
    assert received[0].data["task_id"] == "t1"
    assert received[0].data["role"] == "Researcher"


def test_task_complete_event():
    bus = EventBus()
    received = []
    bus.on("task_complete", lambda e: received.append(e))
    bus.task_complete("r1", "t1", time_s=1.5, output="done")
    assert received[0].data["time_s"] == 1.5
    assert received[0].data["output"] == "done"


def test_task_failed_event():
    bus = EventBus()
    received = []
    bus.on("task_failed", lambda e: received.append(e))
    bus.task_failed("r1", "t1", error="timeout")
    assert received[0].data["error"] == "timeout"


def test_task_waiting_event():
    bus = EventBus()
    received = []
    bus.on("task_waiting", lambda e: received.append(e))
    bus.task_waiting("r1", "t1", reason="approval")
    assert received[0].data["reason"] == "approval"


def test_skill_update_event():
    bus = EventBus()
    received = []
    bus.on("skill_update", lambda e: received.append(e))
    bus.skill_update("r1", "my_skill", 0.85)
    assert received[0].data["fitness"] == 0.85


def test_log_event():
    bus = EventBus()
    received = []
    bus.on("log", lambda e: received.append(e))
    bus.log("r1", "hello world")
    assert received[0].data["message"] == "hello world"


def test_run_complete_event():
    bus = EventBus()
    received = []
    bus.on("run_complete", lambda e: received.append(e))
    bus.run_complete("r1", succeeded=3, total=5, time_s=2.5)
    assert received[0].data["succeeded"] == 3
    assert received[0].data["total"] == 5


# ── Global bus ──

def test_global_bus_get_set():
    original = get_event_bus()
    new_bus = EventBus()
    set_event_bus(new_bus)
    assert get_event_bus() is new_bus
    set_event_bus(original)  # restore


# ── Stream generator ──

def test_stream_yields_emitted_events():
    bus = EventBus()
    bus.emit(Event("a"))
    bus.emit(Event("b"))
    gen = bus.stream(timeout=0.1)
    assert next(gen).type == "a"
    assert next(gen).type == "b"
    # Next call should timeout and yield None (heartbeat)
    assert next(gen) is None
