"""Streaming — real-time LLM output streaming for Agent Swarm.

Zero dependencies. Works with any async generator LLM.

Usage:
    from agent_swarm.streaming import StreamingAdapter, StreamCollector

    # Wrap a streaming LLM
    async def my_streaming_llm(prompt, tools=None):
        async for chunk in openai_stream(prompt):
            yield chunk

    adapter = StreamingAdapter(my_streaming_llm)
    adapter.on_token(lambda token, task_id: print(token, end=""))

    swarm = Swarm(llm=adapter.as_llm())

    # Or collect chunks manually
    collector = StreamCollector()
    adapter.on_token(collector.collect)
    result = await swarm.run("goal", tasks=[...])
    print(collector.get("task_id"))  # Full text for a task
"""

__all__ = ['StreamEvent', 'StreamCollector', 'StreamingAdapter', 'streaming_print']
import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Dict, List, Optional


@dataclass
class StreamEvent:
    """A single streaming event."""
    type: str           # token, start, end, error
    task_id: str = ""
    content: str = ""
    timestamp: float = field(default_factory=time.time)


class StreamCollector:
    """Collects streaming tokens by task_id."""

    def __init__(self):
        self._buffers: Dict[str, List[str]] = {}
        self._timestamps: Dict[str, float] = {}
        self.total_tokens = 0

    def collect(self, token: str, task_id: str = ""):
        """Collect a token chunk."""
        if task_id not in self._buffers:
            self._buffers[task_id] = []
            self._timestamps[task_id] = time.time()
        self._buffers[task_id].append(token)
        self.total_tokens += 1

    def get(self, task_id: str) -> str:
        """Get full collected text for a task."""
        return "".join(self._buffers.get(task_id, []))

    def get_all(self) -> Dict[str, str]:
        """Get all collected text by task_id."""
        return {tid: "".join(chunks) for tid, chunks in self._buffers.items()}

    def clear(self):
        self._buffers.clear()
        self._timestamps.clear()
        self.total_tokens = 0


class StreamingAdapter:
    """Adapts streaming LLMs to work with Agent Swarm.

    Agent Swarm's core engine expects: async def llm(prompt, tools) -> str
    Streaming LLMs produce: async def llm(prompt, tools) -> AsyncIterator[str]

    This adapter bridges the gap: collects chunks while emitting real-time events.
    """

    def __init__(self, streaming_llm: Callable):
        """
        Args:
            streaming_llm: An async generator function that yields string chunks.
                          async def my_llm(prompt, tools=None) -> AsyncIterator[str]:
                              async for chunk in api_stream(...):
                                  yield chunk.text
        """
        self._streaming_llm = streaming_llm
        self._token_callbacks: List[Callable] = []
        self._event_callbacks: List[Callable] = []
        self._current_task_id = ""

    def on_token(self, callback: Callable):
        """Register callback for each token: callback(token: str, task_id: str)"""
        self._token_callbacks.append(callback)
        return self

    def on_event(self, callback: Callable):
        """Register callback for stream events: callback(StreamEvent)"""
        self._event_callbacks.append(callback)
        return self

    def _emit_event(self, event: StreamEvent):
        for cb in self._event_callbacks:
            try:
                cb(event)
            except Exception:
                pass

    def _emit_token(self, token: str, task_id: str):
        for cb in self._token_callbacks:
            try:
                cb(token, task_id)
            except Exception:
                pass

    def as_llm(self) -> Callable:
        """Return a function compatible with Swarm(llm=...)."""
        adapter = self

        async def llm_wrapper(prompt: str, tools=None):
            task_id = adapter._current_task_id
            adapter._emit_event(StreamEvent("start", task_id))

            chunks = []
            usage = None
            try:
                result = adapter._streaming_llm(prompt, tools)
                # Check if it's an async generator
                if hasattr(result, '__aiter__'):
                    async for chunk in result:
                        if isinstance(chunk, tuple) and len(chunk) == 2:
                            text, meta = chunk
                            if isinstance(meta, dict) and "total_tokens" in meta:
                                usage = meta
                            chunks.append(str(text))
                        else:
                            chunks.append(str(chunk))
                        adapter._emit_token(chunks[-1], task_id)
                elif asyncio.iscoroutine(result):
                    # Not actually streaming — just a regular async function
                    raw = await result
                    if isinstance(raw, tuple) and len(raw) == 2:
                        return raw  # (output, usage)
                    return raw
                else:
                    # Sync generator or other
                    raw = await asyncio.ensure_future(result) if asyncio.iscoroutine(result) else result
                    return str(raw) if raw is not None else ""
            except Exception as e:
                adapter._emit_event(StreamEvent("error", task_id, str(e)))
                raise

            output = "".join(chunks)
            adapter._emit_event(StreamEvent("end", task_id, f"{len(chunks)} chunks"))

            if usage:
                return (output, usage)
            return output

        return llm_wrapper

    def set_task_id(self, task_id: str):
        """Set current task ID for token attribution."""
        self._current_task_id = task_id


def streaming_print(token: str, task_id: str = ""):
    """Simple print callback for streaming — prints tokens as they arrive."""
    import sys
    sys.stdout.write(token)
    sys.stdout.flush()
