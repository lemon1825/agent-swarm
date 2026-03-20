"""JSONL Telemetry for Agent Swarm.

Thread-safe event logging to JSONL files with read-back and aggregation.
"""
from __future__ import annotations
import json
import os
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class TelemetryEvent:
    event_type: str  # skill_retrieved, skill_promoted, run_completed, qa_score, task_completed, error_occurred
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class TelemetryWriter:
    """Thread-safe JSONL telemetry writer."""

    def __init__(self, path: str):
        self._path = path
        self._lock = threading.Lock()

    @property
    def path(self) -> str:
        return self._path

    def emit(self, event_type: str, data: Optional[Dict[str, Any]] = None) -> TelemetryEvent:
        """Write a telemetry event to the JSONL file."""
        event = TelemetryEvent(event_type=event_type, data=data or {})
        line = json.dumps(asdict(event), default=str)
        with self._lock:
            dir_path = os.path.dirname(self._path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        return event

    def emit_event(self, event: TelemetryEvent) -> None:
        """Write a pre-built event."""
        line = json.dumps(asdict(event), default=str)
        with self._lock:
            dir_path = os.path.dirname(self._path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line + "\n")


class TelemetryReader:
    """Read and aggregate JSONL telemetry data."""

    def __init__(self, path: str):
        self._path = path

    def read_all(self) -> List[TelemetryEvent]:
        """Read all events from the JSONL file."""
        events = []
        if not os.path.exists(self._path):
            return events
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        d = json.loads(line)
                        events.append(TelemetryEvent(**d))
                    except (json.JSONDecodeError, TypeError):
                        pass
        return events

    def filter_by_type(self, event_type: str) -> List[TelemetryEvent]:
        """Filter events by type."""
        return [e for e in self.read_all() if e.event_type == event_type]

    def count_by_type(self) -> Dict[str, int]:
        """Count events grouped by type."""
        counts: Dict[str, int] = {}
        for event in self.read_all():
            counts[event.event_type] = counts.get(event.event_type, 0) + 1
        return counts

    def aggregate_stats(self) -> Dict[str, Any]:
        """Aggregate statistics from all events."""
        events = self.read_all()
        if not events:
            return {"total_events": 0, "event_types": {}, "time_range_s": 0}

        counts: Dict[str, int] = {}
        for e in events:
            counts[e.event_type] = counts.get(e.event_type, 0) + 1

        timestamps = [e.timestamp for e in events if e.timestamp > 0]
        time_range = (max(timestamps) - min(timestamps)) if len(timestamps) > 1 else 0

        return {
            "total_events": len(events),
            "event_types": counts,
            "time_range_s": round(time_range, 2),
            "first_event": min(timestamps) if timestamps else 0,
            "last_event": max(timestamps) if timestamps else 0,
        }
