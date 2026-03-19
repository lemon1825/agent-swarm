"""Tests for result_export.py — save_result in md/html/json formats."""
import json
import os
import pytest
from dataclasses import dataclass, field
from typing import Optional, List

from agent_swarm.result_export import save_result, _to_markdown, _to_html, _escape, _inline


@dataclass
class _MockTaskResult:
    """Mimics core.TaskResult for testing."""
    output: Optional[str] = None
    error: Optional[str] = None
    role: str = ""
    validation_failures: List[str] = field(default_factory=list)

    @property
    def success(self):
        return self.error is None and not self.validation_failures


def _make_result(succeeded=2, total=3, goal="Test Goal"):
    return {
        "metadata": {
            "goal": goal,
            "succeeded": succeeded,
            "total_tasks": total,
            "waves": 1,
            "execution_time_s": 1.5,
        },
        "results": {
            "task1": _MockTaskResult(output="Result 1", role="Researcher"),
            "task2": _MockTaskResult(output="Result 2", role="Writer"),
            "task3": _MockTaskResult(error="timeout", role="Reviewer"),
        },
        "final_output": "Final summary output",
    }


# ── Markdown ──

def test_save_result_markdown(tmp_path):
    path = str(tmp_path / "report.md")
    result = _make_result()
    abs_path = save_result(result, path)
    assert os.path.isfile(abs_path)
    content = open(path, encoding="utf-8").read()
    assert "# Test Goal" in content
    assert "2/3 succeeded" in content
    assert "Result 1" in content
    assert "timeout" in content
    assert "Final summary output" in content


def test_markdown_format():
    result = _make_result()
    md = _to_markdown(result)
    assert md.startswith("# Test Goal")
    assert "## Summary" in md
    assert "## Results" in md


# ── HTML ──

def test_save_result_html(tmp_path):
    path = str(tmp_path / "report.html")
    result = _make_result()
    abs_path = save_result(result, path)
    content = open(path, encoding="utf-8").read()
    assert "<!DOCTYPE html>" in content
    assert "<title>Test Goal</title>" in content
    assert "Result 1" in content


def test_html_format():
    result = _make_result()
    html = _to_html(result)
    assert "<h1>" in html
    assert "<style>" in html


# ── JSON ──

def test_save_result_json(tmp_path):
    path = str(tmp_path / "report.json")
    # Use simple dict results for JSON serialization
    result = {
        "metadata": {"goal": "Test", "succeeded": 1, "total_tasks": 1},
        "results": {"t1": {"output": "done"}},
    }
    abs_path = save_result(result, path)
    content = open(path, encoding="utf-8").read()
    data = json.loads(content)
    assert data["metadata"]["goal"] == "Test"


# ── Unknown extension defaults to markdown ──

def test_save_result_unknown_ext(tmp_path):
    path = str(tmp_path / "report.txt")
    result = _make_result()
    save_result(result, path)
    content = open(path, encoding="utf-8").read()
    assert "# Test Goal" in content


# ── Edge cases ──

def test_empty_result(tmp_path):
    path = str(tmp_path / "empty.md")
    result = {"metadata": {}, "results": {}}
    save_result(result, path)
    content = open(path, encoding="utf-8").read()
    assert "Agent Swarm Report" in content


def test_escape():
    assert _escape("<script>") == "&lt;script&gt;"
    assert _escape('a "b" c') == 'a &quot;b&quot; c'


def test_inline():
    result = _inline("**bold** and *italic* and `code`")
    assert "<strong>bold</strong>" in result
    assert "<em>italic</em>" in result
    assert "<code>code</code>" in result
