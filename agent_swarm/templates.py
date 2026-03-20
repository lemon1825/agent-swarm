"""Template System for Agent Swarm.

Structured output templates with section-based rendering.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import re


@dataclass
class TemplateSection:
    """A section within a template."""
    name: str
    content_template: str  # String with {placeholder} syntax
    required: bool = True
    prefix: str = ""  # e.g., "## " for markdown headers
    suffix: str = ""


@dataclass
class Template:
    """A structured output template."""
    name: str
    description: str = ""
    sections: List[TemplateSection] = field(default_factory=list)
    separator: str = "\n\n"
    header: str = ""
    footer: str = ""


class TemplateRenderer:
    """Renders templates with data."""

    @staticmethod
    def render(template: Template, data: Dict[str, Any]) -> str:
        """Fill placeholders in template sections. Skip optional empty sections."""
        parts = []
        safe = _SafeDict(data)

        if template.header:
            parts.append(template.header.format_map(_SafeDict(data)))

        for section in template.sections:
            try:
                content = section.content_template.format_map(_SafeDict(data))
            except (KeyError, ValueError):
                content = ""

            # Skip optional sections with no content
            if not section.required and not content.strip():
                continue

            rendered = ""
            if section.prefix:
                rendered += section.prefix
            rendered += f"{section.name}\n{content}"
            if section.suffix:
                rendered += section.suffix
            parts.append(rendered)

        result = template.separator.join(parts)

        if template.footer:
            result += template.separator + template.footer.format_map(_SafeDict(data))

        return result

    @staticmethod
    def validate(template: Template, data: Dict[str, Any]) -> List[str]:
        """Check required fields are present in data. Return list of missing fields."""
        missing = []
        for section in template.sections:
            if not section.required:
                continue
            placeholders = re.findall(r'\{(\w+)\}', section.content_template)
            for ph in placeholders:
                if ph not in data:
                    missing.append(f"{section.name}: {ph}")
        return missing


class _SafeDict(dict):
    """Dict that returns empty string for missing keys instead of raising KeyError."""
    def __missing__(self, key: str) -> str:
        return ""


# ─── Built-in Templates ───

QA_REPORT = Template(
    name="QA Report",
    description="Quality assurance report with health score",
    header="# QA Report",
    sections=[
        TemplateSection(name="Summary", content_template="{summary}", required=True, prefix="## "),
        TemplateSection(name="Health Score", content_template="Score: {health_score}/100 (Grade: {grade})", required=True, prefix="## "),
        TemplateSection(name="Issues", content_template="{issues}", required=True, prefix="## "),
        TemplateSection(name="Recommendations", content_template="{recommendations}", required=False, prefix="## "),
    ],
)

TODO_LIST = Template(
    name="TODO List",
    description="Task list with status and priority",
    sections=[
        TemplateSection(name="Tasks", content_template="{tasks}", required=True, prefix="## "),
        TemplateSection(name="Blocked", content_template="{blocked}", required=False, prefix="## "),
        TemplateSection(name="Completed", content_template="{completed}", required=False, prefix="## "),
    ],
)

DESIGN_REVIEW = Template(
    name="Design Review",
    description="Design review with pros, cons, and risks",
    sections=[
        TemplateSection(name="Overview", content_template="{overview}", required=True, prefix="## "),
        TemplateSection(name="Pros", content_template="{pros}", required=True, prefix="## "),
        TemplateSection(name="Cons", content_template="{cons}", required=True, prefix="## "),
        TemplateSection(name="Risks", content_template="{risks}", required=True, prefix="## "),
        TemplateSection(name="Recommendation", content_template="{recommendation}", required=True, prefix="## "),
    ],
)

RETRO_REPORT = Template(
    name="Retrospective Report",
    description="Retrospective with metrics and action items",
    header="# Retrospective Report — {period}",
    sections=[
        TemplateSection(name="Metrics", content_template="{metrics}", required=True, prefix="## "),
        TemplateSection(name="Patterns", content_template="{patterns}", required=True, prefix="## "),
        TemplateSection(name="Improvements", content_template="{improvements}", required=False, prefix="## "),
        TemplateSection(name="Action Items", content_template="{action_items}", required=True, prefix="## "),
    ],
)
