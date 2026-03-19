"""Tests for streaming.py — StreamEvent, StreamCollector, StreamingAdapter."""
import asyncio
import pytest
from agent_swarm.streaming import StreamEvent, StreamCollector, StreamingAdapter


# ── StreamEvent ──

def test_stream_event_creation():
    e = StreamEvent(type="token", task_id="t1", content="hello")
    assert e.type == "token"
    assert e.task_id == "t1"
    assert e.content == "hello"
    assert e.timestamp > 0


def test_stream_event_defaults():
    e = StreamEvent(type="start")
    assert e.task_id == ""
    assert e.content == ""


# ── StreamCollector ──

def test_collector_collect_and_get():
    c = StreamCollector()
    c.collect("hello ", "t1")
    c.collect("world", "t1")
    assert c.get("t1") == "hello world"
    assert c.total_tokens == 2


def test_collector_multiple_tasks():
    c = StreamCollector()
    c.collect("a", "t1")
    c.collect("b", "t2")
    assert c.get("t1") == "a"
    assert c.get("t2") == "b"


def test_collector_get_nonexistent():
    c = StreamCollector()
    assert c.get("missing") == ""


def test_collector_get_all():
    c = StreamCollector()
    c.collect("x", "t1")
    c.collect("y", "t2")
    all_texts = c.get_all()
    assert all_texts["t1"] == "x"
    assert all_texts["t2"] == "y"


def test_collector_clear():
    c = StreamCollector()
    c.collect("data", "t1")
    c.clear()
    assert c.get("t1") == ""
    assert c.total_tokens == 0


# ── StreamingAdapter ──

def test_adapter_with_async_generator():
    async def streaming_llm(prompt, tools=None):
        for chunk in ["Hello", " ", "World"]:
            yield chunk

    adapter = StreamingAdapter(streaming_llm)
    tokens = []
    adapter.on_token(lambda t, tid: tokens.append(t))

    llm = adapter.as_llm()
    result = asyncio.run(llm("test prompt"))
    assert result == "Hello World"
    assert tokens == ["Hello", " ", "World"]


def test_adapter_with_coroutine():
    async def regular_llm(prompt, tools=None):
        return "direct result"

    adapter = StreamingAdapter(regular_llm)
    llm = adapter.as_llm()
    result = asyncio.run(llm("test"))
    assert result == "direct result"


def test_adapter_events():
    async def streaming_llm(prompt, tools=None):
        yield "chunk"

    adapter = StreamingAdapter(streaming_llm)
    events = []
    adapter.on_event(lambda e: events.append(e))

    llm = adapter.as_llm()
    asyncio.run(llm("test"))

    types = [e.type for e in events]
    assert "start" in types
    assert "end" in types


def test_adapter_set_task_id():
    async def streaming_llm(prompt, tools=None):
        yield "data"

    adapter = StreamingAdapter(streaming_llm)
    adapter.set_task_id("my_task")

    events = []
    adapter.on_event(lambda e: events.append(e))

    llm = adapter.as_llm()
    asyncio.run(llm("test"))
    assert events[0].task_id == "my_task"


def test_adapter_error_handling():
    async def failing_llm(prompt, tools=None):
        raise ValueError("LLM error")
        yield  # make it a generator

    adapter = StreamingAdapter(failing_llm)
    llm = adapter.as_llm()
    with pytest.raises(ValueError, match="LLM error"):
        asyncio.run(llm("test"))


def test_adapter_with_usage_tuple():
    async def streaming_llm(prompt, tools=None):
        yield ("Hello", {"total_tokens": 10})
        yield ("World", {"total_tokens": 20})

    adapter = StreamingAdapter(streaming_llm)
    llm = adapter.as_llm()
    result = asyncio.run(llm("test"))
    assert isinstance(result, tuple)
    assert result[0] == "HelloWorld"


def test_adapter_bad_callback_isolated():
    async def streaming_llm(prompt, tools=None):
        yield "data"

    adapter = StreamingAdapter(streaming_llm)
    adapter.on_token(lambda t, tid: (_ for _ in ()).throw(ValueError("boom")))

    llm = adapter.as_llm()
    result = asyncio.run(llm("test"))
    assert result == "data"


def test_collector_with_adapter():
    async def streaming_llm(prompt, tools=None):
        for chunk in ["Part1", "Part2", "Part3"]:
            yield chunk

    adapter = StreamingAdapter(streaming_llm)
    collector = StreamCollector()
    adapter.set_task_id("task_a")
    adapter.on_token(collector.collect)

    llm = adapter.as_llm()
    asyncio.run(llm("test"))
    assert collector.get("task_a") == "Part1Part2Part3"
    assert collector.total_tokens == 3
