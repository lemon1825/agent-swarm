"""Session protocol — pluggable cross-run memory backend."""
from __future__ import annotations
from typing import Dict, Protocol, runtime_checkable

@runtime_checkable
class SessionStore(Protocol):
    def load_session(self, session_id: str) -> Dict: ...
    def save_session(self, session_id: str, data: Dict) -> None: ...
    def append_memory(self, session_id: str, item: Dict) -> None: ...

class InMemorySessionStore:
    def __init__(self): self._store: Dict[str, Dict] = {}
    def load_session(self, sid): return self._store.get(sid, {"memory": [], "runs": [], "metadata": {}})
    def save_session(self, sid, data): self._store[sid] = data
    def append_memory(self, sid, item):
        s = self.load_session(sid)
        s.setdefault("memory", []).append(item)
        self.save_session(sid, s)
