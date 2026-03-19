"""Tests for metrics.py — Span, Tracer, MetricsCollector."""
import time
import pytest
from agent_swarm.metrics import Span, Tracer, MetricsCollector


# ── Span ──

def test_span_creation():
    s = Span(name="test_span")
    assert s.name == "test_span"
    assert len(s.span_id) == 8
    assert s.status == "ok"
    assert s.children == []


def test_span_duration_ms():
    s = Span(name="test", start_time=1.0, end_time=1.5)
    assert s.duration_ms == 500.0


def test_span_duration_ms_no_end():
    s = Span(name="test", start_time=1.0)
    assert s.duration_ms == 0


def test_span_to_dict():
    s = Span(name="test", task_id="t1", start_time=1.0, end_time=2.0, detail="some detail")
    d = s.to_dict()
    assert d["name"] == "test"
    assert d["task_id"] == "t1"
    assert d["duration_ms"] == 1000.0
    assert d["detail"] == "some detail"


def test_span_detail_truncated():
    s = Span(name="test", detail="x" * 300)
    d = s.to_dict()
    assert len(d["detail"]) == 200


# ── Tracer ──

def test_tracer_start_end():
    t = Tracer()
    s = t.start("op1")
    assert s.name == "op1"
    ended = t.end()
    assert ended is s
    assert ended.end_time > 0
    assert ended.status == "ok"


def test_tracer_nested_spans():
    t = Tracer()
    parent = t.start("parent")
    child = t.start("child")
    assert child.parent_id == parent.span_id
    assert child.span_id in parent.children
    t.end()
    t.end()
    assert len(t.spans) == 2


def test_tracer_end_empty_stack():
    t = Tracer()
    result = t.end()
    assert result is None


def test_tracer_end_with_status():
    t = Tracer()
    t.start("op")
    ended = t.end(status="error", detail="something broke")
    assert ended.status == "error"
    assert ended.detail == "something broke"


def test_tracer_to_dict():
    t = Tracer()
    t.start("op1")
    t.end()
    d = t.to_dict()
    assert d["total_spans"] == 1
    assert len(d["spans"]) == 1


# ── MetricsCollector ──

def test_metrics_initial_state():
    m = MetricsCollector()
    assert m.total_runs == 0
    assert m.total_tasks == 0
    assert m.total_retries == 0


def test_metrics_record_run():
    m = MetricsCollector()
    m.record_run({"total_tasks": 5, "succeeded": 4, "failed": 1, "llm_calls_used": 10})
    assert m.total_runs == 1
    assert m.total_tasks == 5
    assert m.succeeded_tasks == 4
    assert m.failed_tasks == 1
    assert m.total_llm_calls == 10


def test_metrics_record_task_duration():
    m = MetricsCollector()
    m.record_task_duration(100.0)
    m.record_task_duration(200.0)
    assert len(m._task_durations) == 2


def test_metrics_record_retry():
    m = MetricsCollector()
    m.record_retry()
    m.record_retry()
    assert m.total_retries == 2


def test_metrics_record_validation_failure():
    m = MetricsCollector()
    m.record_validation_failure("missing field")
    m.record_validation_failure("missing field")
    m.record_validation_failure("bad type")
    assert m._validation_failures["missing field"] == 2
    assert m._validation_failures["bad type"] == 1


# ── Percentiles ──

def test_percentiles_empty():
    result = MetricsCollector._percentiles([])
    assert result["count"] == 0
    assert result["avg"] == 0


def test_percentiles_small():
    result = MetricsCollector._percentiles([10.0, 20.0, 30.0])
    assert result["count"] == 3
    assert result["min"] == 10.0
    assert result["max"] == 30.0
    assert result["avg"] == 20.0
    assert result["p50"] == 20.0
    # p95/p99 fallback to max for small datasets
    assert result["p95"] == 30.0
    assert result["p99"] == 30.0


def test_percentiles_large():
    values = list(range(100))
    result = MetricsCollector._percentiles(values)
    assert result["count"] == 100
    assert result["min"] == 0
    assert result["max"] == 99.0
    assert result["p95"] == 95.0
    assert result["p99"] == 99.0


# ── to_dict ──

def test_metrics_to_dict():
    m = MetricsCollector()
    m.record_run({"total_tasks": 10, "succeeded": 8, "failed": 2})
    m.record_task_duration(100.0)
    m.record_retry()
    d = m.to_dict()
    assert d["total_runs"] == 1
    assert d["success_rate"] == 0.8
    assert d["total_retries"] == 1
    assert d["task_duration_ms"]["count"] == 1
    assert "evolution" in d
    assert "shadow" in d
    assert "top_validation_failures" in d
