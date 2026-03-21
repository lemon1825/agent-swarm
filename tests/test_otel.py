"""Tests for OTelSpan and TraceExporter (NVIDIA Observability)."""
import json
import os
import tempfile
import time
import pytest
from agent_swarm.tracing import OTelSpan, TraceExporter, Trace, TraceNode


class TestOTelSpan:
    def test_frozen(self):
        s = OTelSpan(trace_id="a", span_id="b")
        with pytest.raises(AttributeError):
            s.trace_id = "c"

    def test_generate_trace_id_length(self):
        tid = OTelSpan.generate_trace_id()
        assert len(tid) == 32  # 16 bytes = 32 hex chars

    def test_generate_span_id_length(self):
        sid = OTelSpan.generate_span_id()
        assert len(sid) == 16  # 8 bytes = 16 hex chars

    def test_ids_are_unique(self):
        ids = {OTelSpan.generate_span_id() for _ in range(100)}
        assert len(ids) == 100

    def test_default_status_unset(self):
        s = OTelSpan(trace_id="a", span_id="b")
        assert s.status == "UNSET"

    def test_status_codes(self):
        s1 = OTelSpan(trace_id="a", span_id="b", status="UNSET")
        s2 = OTelSpan(trace_id="a", span_id="b", status="OK")
        s3 = OTelSpan(trace_id="a", span_id="b", status="ERROR")
        assert s1.to_otel_dict()["status"]["code"] == 0
        assert s2.to_otel_dict()["status"]["code"] == 1
        assert s3.to_otel_dict()["status"]["code"] == 2

    def test_to_otel_dict_structure(self):
        s = OTelSpan(
            trace_id="abc123", span_id="def456",
            parent_span_id="parent1",
            operation_name="test_op",
            start_time_ns=1000, end_time_ns=2000,
            status="OK",
            attributes=(("key", "val"), ("count", 42)),
        )
        d = s.to_otel_dict()
        assert d["traceId"] == "abc123"
        assert d["spanId"] == "def456"
        assert d["parentSpanId"] == "parent1"
        assert d["operationName"] == "test_op"
        assert d["startTimeUnixNano"] == 1000
        assert d["endTimeUnixNano"] == 2000
        assert d["status"]["code"] == 1

    def test_no_parent_span_omitted(self):
        s = OTelSpan(trace_id="a", span_id="b")
        d = s.to_otel_dict()
        assert "parentSpanId" not in d

    def test_add_event_returns_new_span(self):
        s1 = OTelSpan(trace_id="a", span_id="b")
        s2 = s1.add_event("error", {"message": "failed"})
        assert len(s1.events) == 0  # original unchanged
        assert len(s2.events) == 1
        assert s2.events[0]["name"] == "error"
        d = s2.to_otel_dict()
        assert "events" in d

    def test_attributes_types(self):
        s = OTelSpan(
            trace_id="a", span_id="b",
            attributes=(("str_val", "hello"), ("int_val", 42), ("float_val", 3.14), ("bool_val", True)),
        )
        d = s.to_otel_dict()
        attrs = {a["key"]: a["value"] for a in d["attributes"]}
        assert attrs["str_val"] == {"stringValue": "hello"}
        assert attrs["int_val"] == {"intValue": "42"}
        assert attrs["float_val"] == {"doubleValue": 3.14}
        assert attrs["bool_val"] == {"boolValue": True}


class TestTraceExporter:
    def _make_trace(self):
        t = Trace(run_id="run-1", mission="Test mission", start_time=time.time() - 1)
        t.end_time = time.time()
        t.tasks_succeeded = 2
        t.tasks_failed = 1
        t.total_tokens = 1000
        t.total_cost_usd = 0.05
        t.nodes["t1"] = TraceNode(
            id="t1", type="task_complete", name="Research",
            role="Researcher", status="success",
            start_time=t.start_time, end_time=t.end_time,
        )
        t.nodes["t2"] = TraceNode(
            id="t2", type="task_complete", name="Analysis",
            role="Analyst", status="success",
            start_time=t.start_time, end_time=t.end_time,
            dependencies=["t1"],
        )
        t.nodes["t3"] = TraceNode(
            id="t3", type="task_failed", name="Report",
            role="Writer", status="failed", error="timeout",
            start_time=t.start_time, end_time=t.end_time,
            dependencies=["t2"],
        )
        return t

    def test_trace_to_otel_structure(self):
        t = self._make_trace()
        otel = TraceExporter.trace_to_otel(t)
        assert "resourceSpans" in otel
        rs = otel["resourceSpans"][0]
        assert "resource" in rs
        assert "scopeSpans" in rs
        spans = rs["scopeSpans"][0]["spans"]
        # 1 root span + 3 task spans
        assert len(spans) == 4

    def test_root_span_has_run_info(self):
        t = self._make_trace()
        otel = TraceExporter.trace_to_otel(t)
        root_span = otel["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        assert "run:" in root_span["operationName"]
        assert root_span["status"]["code"] == 2  # ERROR (has failures)

    def test_failed_task_has_event(self):
        t = self._make_trace()
        otel = TraceExporter.trace_to_otel(t)
        spans = otel["resourceSpans"][0]["scopeSpans"][0]["spans"]
        error_spans = [s for s in spans if s["status"]["code"] == 2 and "events" in s]
        assert len(error_spans) >= 1

    def test_export_json_file(self):
        t = self._make_trace()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            TraceExporter.export_json(t, path)
            with open(path) as f:
                data = json.load(f)
            assert "resourceSpans" in data
        finally:
            os.unlink(path)

    def test_service_name(self):
        t = self._make_trace()
        otel = TraceExporter.trace_to_otel(t)
        resource_attrs = otel["resourceSpans"][0]["resource"]["attributes"]
        svc = next(a for a in resource_attrs if a["key"] == "service.name")
        assert svc["value"]["stringValue"] == "agent-swarm"
