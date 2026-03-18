"""Memory — persistent agent memory across runs.

Zero external dependencies. File-based JSON storage.
Short-term (per-run), long-term (across runs), entity (named objects), and contextual (skill lessons).

Usage:
    from agent_swarm.memory import MemoryStore

    memory = MemoryStore("./agent_memory")
    memory.add("short", "User prefers concise output", run_id=1)
    memory.add("long", "Project uses FastAPI backend", tags=["architecture"])
    memory.add("entity", "CompanyX: AI startup, 50 employees", entity="CompanyX")
    memory.add("context", "YAML parsing requires careful indentation", skill="YAMLParser")

    # Retrieve relevant memories
    relevant = memory.search("FastAPI deployment")
    # → Returns ranked memories by relevance

    # Use with Swarm
    swarm = Swarm(llm=my_llm, memory=memory)
"""

__all__ = ['Memory', 'MemoryStore']
import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Set


@dataclass
class Memory:
    """A single memory entry."""
    id: str
    type: str              # short, long, entity, context
    content: str
    tags: List[str] = field(default_factory=list)
    entity: str = ""       # For entity memory
    skill: str = ""        # For context/skill memory
    run_id: int = 0
    timestamp: float = field(default_factory=time.time)
    access_count: int = 0
    relevance_score: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> 'Memory':
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class MemoryStore:
    """Persistent memory store — file-based, zero dependencies.

    Memory types:
        short   — current run context (cleared after run)
        long    — persistent facts, preferences, patterns
        entity  — named entities (people, companies, projects)
        context — skill-specific lessons and patterns
    """

    def __init__(self, path: str = None, max_memories: int = 1000):
        self.path = path or os.path.expanduser("~/.agent-swarm/memory")
        self.max_memories = max_memories
        self._memories: Dict[str, Memory] = {}
        self._id_counter = 0
        self._load()

    def _file(self) -> str:
        return os.path.join(self.path, "memories.json")

    def _load(self):
        f = self._file()
        if os.path.isfile(f):
            try:
                with open(f) as fh:
                    data = json.load(fh)
                for d in data.get("memories", []):
                    m = Memory.from_dict(d)
                    self._memories[m.id] = m
                self._id_counter = data.get("id_counter", len(self._memories))
            except Exception:
                pass

    def _save(self):
        os.makedirs(self.path, exist_ok=True)
        with open(self._file(), "w") as fh:
            json.dump({
                "memories": [m.to_dict() for m in self._memories.values()],
                "id_counter": self._id_counter,
            }, fh, indent=2, ensure_ascii=False, default=str)

    def add(self, type: str, content: str, tags: List[str] = None,
            entity: str = "", skill: str = "", run_id: int = 0) -> Memory:
        """Add a memory."""
        self._id_counter += 1
        m = Memory(
            id=f"mem_{self._id_counter}",
            type=type, content=content,
            tags=tags or [], entity=entity, skill=skill, run_id=run_id,
        )
        self._memories[m.id] = m

        # Evict oldest if over limit
        if len(self._memories) > self.max_memories:
            self._evict()

        self._save()
        return m

    def _evict(self):
        """Remove least-accessed short-term memories first, then oldest."""
        shorts = [m for m in self._memories.values() if m.type == "short"]
        if shorts:
            shorts.sort(key=lambda m: (m.access_count, m.timestamp))
            del self._memories[shorts[0].id]
            return
        all_sorted = sorted(self._memories.values(), key=lambda m: (m.access_count, m.timestamp))
        if all_sorted:
            del self._memories[all_sorted[0].id]

    def search(self, query: str, type: str = None, limit: int = 10,
               run_id: int = None, entity: str = None) -> List[Memory]:
        """Search memories by keyword relevance."""
        query_words = set(query.lower().split())
        results = []

        for m in self._memories.values():
            if type and m.type != type:
                continue
            if run_id is not None and m.type == "short" and m.run_id != run_id:
                continue
            if entity and m.entity.lower() != entity.lower():
                continue

            # Simple keyword relevance
            content_words = set(m.content.lower().split())
            tag_words = set(t.lower() for t in m.tags)
            all_words = content_words | tag_words | {m.entity.lower(), m.skill.lower()}

            overlap = len(query_words & all_words)
            if overlap == 0:
                continue

            # Score: keyword overlap + recency bonus + access frequency
            recency = 1.0 / (1.0 + (time.time() - m.timestamp) / 86400)  # Decay over days
            score = overlap * 2.0 + recency * 0.5 + m.access_count * 0.1

            # Boost long-term and entity memories
            if m.type == "long":
                score *= 1.5
            elif m.type == "entity":
                score *= 1.3

            m.relevance_score = round(score, 3)
            results.append(m)

        results.sort(key=lambda m: m.relevance_score, reverse=True)

        # Update access counts
        for m in results[:limit]:
            m.access_count += 1

        if results:
            self._save()

        return results[:limit]

    def get_entity(self, name: str) -> List[Memory]:
        """Get all memories about a specific entity."""
        return [m for m in self._memories.values() if m.entity.lower() == name.lower()]

    def get_context(self, skill: str) -> List[Memory]:
        """Get contextual memories for a specific skill."""
        return [m for m in self._memories.values() if m.skill.lower() == skill.lower()]

    def clear_short_term(self, run_id: int = None):
        """Clear short-term memories, optionally for a specific run."""
        to_remove = [
            m.id for m in self._memories.values()
            if m.type == "short" and (run_id is None or m.run_id == run_id)
        ]
        for mid in to_remove:
            del self._memories[mid]
        self._save()

    def format_for_prompt(self, query: str, max_tokens: int = 500) -> str:
        """Format relevant memories for inclusion in LLM prompt."""
        memories = self.search(query, limit=8)
        if not memories:
            return ""

        lines = ["[Agent Memory]"]
        char_count = 0
        approx_max = max_tokens * 4  # rough chars-to-tokens

        for m in memories:
            entry = f"  [{m.type}] {m.content}"
            if m.entity:
                entry += f" (entity: {m.entity})"
            if m.tags:
                entry += f" #{' #'.join(m.tags)}"

            if char_count + len(entry) > approx_max:
                break
            lines.append(entry)
            char_count += len(entry)

        return "\n".join(lines)

    def stats(self) -> Dict:
        types = {}
        for m in self._memories.values():
            types[m.type] = types.get(m.type, 0) + 1
        return {
            "total": len(self._memories),
            "by_type": types,
            "entities": len(set(m.entity for m in self._memories.values() if m.entity)),
            "skills": len(set(m.skill for m in self._memories.values() if m.skill)),
            "path": self.path,
        }

    def all(self) -> List[Memory]:
        return list(self._memories.values())

    def delete(self, memory_id: str) -> bool:
        if memory_id in self._memories:
            del self._memories[memory_id]
            self._save()
            return True
        return False
