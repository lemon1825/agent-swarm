"""LLM Response Cache — avoids redundant API calls for identical prompts.

Zero dependencies. In-memory with TTL expiration.

Usage:
    from agent_swarm.cache import LLMCache, cached_llm

    cache = LLMCache(max_size=500, ttl_seconds=3600)
    my_cached_llm = cached_llm(original_llm, cache)

    swarm = Swarm(llm=my_cached_llm)
"""

__all__ = ['LLMCache', 'cached_llm']
import hashlib
import time
from typing import Any, Callable, Dict, Optional, Tuple


class LLMCache:
    """In-memory LLM response cache with TTL and size limit."""

    def __init__(self, max_size: int = 500, ttl_seconds: float = 3600):
        self.max_size = max_size
        self.ttl = ttl_seconds
        self._cache: Dict[str, Dict] = {}  # key → {value, usage, timestamp}
        self.hits = 0
        self.misses = 0

    def _key(self, prompt: str, tools: Any = None) -> str:
        h = hashlib.sha256(prompt.encode()).hexdigest()[:24]
        if tools:
            h += "-" + hashlib.sha256(str(tools).encode()).hexdigest()[:8]
        return h

    def get(self, prompt: str, tools: Any = None) -> Optional[Tuple[str, Optional[Dict]]]:
        key = self._key(prompt, tools)
        entry = self._cache.get(key)
        if entry is None:
            self.misses += 1
            return None
        if time.time() - entry["timestamp"] > self.ttl:
            del self._cache[key]
            self.misses += 1
            return None
        self.hits += 1
        return entry["value"], entry.get("usage")

    def put(self, prompt: str, value: str, usage: Optional[Dict] = None, tools: Any = None):
        key = self._key(prompt, tools)
        if len(self._cache) >= self.max_size:
            # Evict oldest entry
            oldest_key = min(self._cache, key=lambda k: self._cache[k]["timestamp"])
            del self._cache[oldest_key]
        self._cache[key] = {"value": value, "usage": usage, "timestamp": time.time()}

    def clear(self):
        self._cache.clear()
        self.hits = 0
        self.misses = 0

    def stats(self) -> Dict:
        total = self.hits + self.misses
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / max(total, 1), 3),
            "ttl_seconds": self.ttl,
        }


def cached_llm(llm_fn: Callable, cache: LLMCache = None) -> Callable:
    """Wrap an LLM function with caching.

    Works with both old-style (returns string) and new-style (returns (string, usage)) LLMs.

    Usage:
        cache = LLMCache(max_size=200, ttl_seconds=1800)
        my_llm = cached_llm(original_openai_llm, cache)
        swarm = Swarm(llm=my_llm)
    """
    if cache is None:
        cache = LLMCache()

    async def wrapper(prompt: str, tools=None):
        # Check cache
        cached = cache.get(prompt, tools)
        if cached is not None:
            value, usage = cached
            if usage:
                return (value, usage)
            return value

        # Call real LLM
        result = await llm_fn(prompt, tools)

        # Store in cache
        if isinstance(result, tuple) and len(result) == 2:
            output, usage = result
            cache.put(prompt, output, usage, tools)
        else:
            cache.put(prompt, result, None, tools)

        return result

    # Attach cache reference for stats access
    wrapper._cache = cache
    return wrapper
