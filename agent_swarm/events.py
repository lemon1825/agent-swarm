"""Event System — real-time execution events for live visualization.

The core engine emits events during swarm.run(). Any listener can subscribe.
Pro dashboard uses this to show real-time DAG progress in the browser.

Usage in core engine:
    from agent_swarm.events import EventBus, Event

    bus = EventBus()
    bus.emit(Event("task_start", {"task_id": "research", "role": "Researcher"}))

Usage as listener:
    bus.on("task_start", lambda e: print(f"Started: {e.data['task_id']}"))

    # Or collect all events
    for event in bus.stream():
        process(event)

HTTP bridge (sends events to Pro dashboard):
    bridge = HttpEventBridge("http://localhost:8000/events/push")
    bus.on_all(bridge.send)
"""
import json
import time
import threading
import queue
import concurrent.futures
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional


@dataclass
class Event:
    """A single execution event."""
    type: str                    # task_start, task_complete, task_failed, phase_change, skill_update, log
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    run_id: str = ""

    def to_dict(self) -> Dict:
        return {"type": self.type, "data": self.data, "timestamp": self.timestamp, "run_id": self.run_id}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


class EventBus:
    """Publish-subscribe event bus for swarm execution events."""

    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}
        self._all_listeners: List[Callable] = []
        self._queue: queue.Queue = queue.Queue(maxsize=1000)
        self._history: List[Event] = []
        self._max_history = 200

    def on(self, event_type: str, callback: Callable):
        """Subscribe to a specific event type."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def on_all(self, callback: Callable):
        """Subscribe to all events."""
        self._all_listeners.append(callback)

    def emit(self, event: Event):
        """Emit an event to all relevant listeners."""
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # Queue for stream()
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            pass

        # Notify typed listeners
        for cb in self._listeners.get(event.type, []):
            try:
                cb(event)
            except Exception:
                pass

        # Notify all-listeners
        for cb in self._all_listeners:
            try:
                cb(event)
            except Exception:
                pass

    def stream(self, timeout: float = 30.0):
        """Generator that yields events as they arrive."""
        while True:
            try:
                event = self._queue.get(timeout=timeout)
                yield event
            except queue.Empty:
                yield None  # Heartbeat

    def history(self) -> List[Event]:
        """Get event history."""
        return list(self._history)

    def clear(self):
        """Clear history and queue."""
        self._history.clear()
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    # ── Convenience emitters ──────────────────────

    def run_start(self, run_id: str, mission: str, tasks: List[Dict]):
        self.emit(Event("run_start", {
            "mission": mission,
            "tasks": [{"id": t.get("id", ""), "name": t.get("name", t.get("description", "")),
                        "role": t.get("role", ""), "deps": t.get("dependencies", t.get("deps", []))}
                       for t in tasks]
        }, run_id=run_id))

    def phase_change(self, run_id: str, phase: str):
        self.emit(Event("phase_change", {"phase": phase}, run_id=run_id))

    def task_start(self, run_id: str, task_id: str, role: str = ""):
        self.emit(Event("task_start", {"task_id": task_id, "role": role}, run_id=run_id))

    def task_complete(self, run_id: str, task_id: str, time_s: float = 0, output: str = ""):
        self.emit(Event("task_complete", {
            "task_id": task_id, "time_s": round(time_s, 2),
            "output": output[:200] if output else ""
        }, run_id=run_id))

    def task_failed(self, run_id: str, task_id: str, error: str = ""):
        self.emit(Event("task_failed", {"task_id": task_id, "error": error[:200]}, run_id=run_id))

    def task_waiting(self, run_id: str, task_id: str, reason: str = "approval"):
        self.emit(Event("task_waiting", {"task_id": task_id, "reason": reason}, run_id=run_id))

    def skill_update(self, run_id: str, name: str, fitness: float):
        self.emit(Event("skill_update", {"name": name, "fitness": round(fitness, 3)}, run_id=run_id))

    def log(self, run_id: str, message: str):
        self.emit(Event("log", {"message": message}, run_id=run_id))

    def run_complete(self, run_id: str, succeeded: int = 0, total: int = 0, time_s: float = 0):
        self.emit(Event("run_complete", {
            "succeeded": succeeded, "total": total, "time_s": round(time_s, 2)
        }, run_id=run_id))


class HttpEventBridge:
    """Sends events to the Pro API via HTTP POST (non-blocking)."""

    def __init__(self, url: str = "http://localhost:8000/events/push"):
        self.url = url
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

    def send(self, event: Event):
        """Send event to Pro API (fire-and-forget in thread pool)."""
        self._executor.submit(self._do_send, event)

    def _do_send(self, event: Event):
        try:
            import urllib.request
            data = event.to_json().encode()
            req = urllib.request.Request(
                self.url, data=data, method="POST",
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=2)
        except Exception:
            pass  # Silently fail — visualization is optional


# Global default bus
_default_bus: Optional[EventBus] = None

def get_event_bus() -> EventBus:
    """Get or create the global event bus."""
    global _default_bus
    if _default_bus is None:
        _default_bus = EventBus()
    return _default_bus

def set_event_bus(bus: EventBus):
    """Set the global event bus."""
    global _default_bus
    _default_bus = bus
