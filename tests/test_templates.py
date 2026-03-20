"""Tests for agent_swarm.templates module."""
import pytest
from agent_swarm.templates import (
    Template, TemplateSection, TemplateRenderer,
    QA_REPORT, TODO_LIST, DESIGN_REVIEW, RETRO_REPORT,
)


def test_template_section_defaults():
    s = TemplateSection(name="Sec", content_template="{x}")
    assert s.required is True
    assert s.prefix == ""
    assert s.suffix == ""


def test_template_creation():
    t = Template(name="T", description="desc")
    assert t.name == "T"
    assert t.sections == []
    assert t.separator == "\n\n"


def test_render_basic_substitution():
    t = Template(name="T", sections=[
        TemplateSection(name="Title", content_template="{title}"),
    ])
    result = TemplateRenderer.render(t, {"title": "Hello"})
    assert "Title\nHello" in result


def test_render_header_footer():
    t = Template(
        name="T",
        header="# {name}",
        footer="--- end {name} ---",
        sections=[TemplateSection(name="Body", content_template="{body}")],
    )
    result = TemplateRenderer.render(t, {"name": "Doc", "body": "content"})
    assert result.startswith("# Doc")
    assert result.endswith("--- end Doc ---")


def test_render_skips_optional_empty():
    t = Template(name="T", sections=[
        TemplateSection(name="Required", content_template="{req}", required=True),
        TemplateSection(name="Optional", content_template="{opt}", required=False),
    ])
    result = TemplateRenderer.render(t, {"req": "data"})
    assert "Required" in result
    assert "Optional" not in result


def test_render_missing_keys_safe():
    t = Template(name="T", sections=[
        TemplateSection(name="S", content_template="val={missing_key}"),
    ])
    result = TemplateRenderer.render(t, {})
    assert "val=" in result  # no KeyError


def test_validate_finds_missing():
    t = Template(name="T", sections=[
        TemplateSection(name="S", content_template="{a} {b}", required=True),
    ])
    missing = TemplateRenderer.validate(t, {"a": "x"})
    assert "S: b" in missing


def test_validate_complete_data():
    t = Template(name="T", sections=[
        TemplateSection(name="S", content_template="{a}", required=True),
    ])
    assert TemplateRenderer.validate(t, {"a": "x"}) == []


def test_qa_report_renders():
    data = {"summary": "OK", "health_score": "95", "grade": "A", "issues": "None"}
    result = TemplateRenderer.render(QA_REPORT, data)
    assert "# QA Report" in result
    assert "Score: 95/100 (Grade: A)" in result


def test_todo_list_renders():
    result = TemplateRenderer.render(TODO_LIST, {"tasks": "- item 1"})
    assert "Tasks" in result
    assert "- item 1" in result


def test_design_review_renders():
    data = {"overview": "o", "pros": "p", "cons": "c", "risks": "r", "recommendation": "rec"}
    result = TemplateRenderer.render(DESIGN_REVIEW, data)
    assert "## Overview" in result
    assert "## Recommendation" in result


def test_retro_report_header_substitution():
    data = {"period": "Sprint 5", "metrics": "m", "patterns": "p", "action_items": "a"}
    result = TemplateRenderer.render(RETRO_REPORT, data)
    assert "# Retrospective Report — Sprint 5" in result
    assert "## Metrics" in result
