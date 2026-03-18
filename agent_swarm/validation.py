"""Validation layer — nested schema, $ref composition, cross-field rules, structured errors."""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

@dataclass
class ValidationError:
    """Structured validation error — debuggable, not just a string."""
    field: str = ""; rule: str = ""; message: str = ""; value: Any = None; path: str = ""
    def __str__(self):
        p = f"{self.path}." if self.path else ""
        return f"{p}{self.field}: {self.message}" if self.field else self.message

@dataclass
class Validator:
    name: str = "BaseValidator"
    def validate(self, c): return (True, "OK") if c and c.strip() else (False, "Empty")

@dataclass
class LengthValidator(Validator):
    name: str = "LengthValidator"; min_length: int = 1; max_length: int = 100000
    def validate(self, c):
        if len(c) < self.min_length: return False, f"Short:{len(c)}<{self.min_length}"
        if len(c) > self.max_length: return False, f"Long"
        return True, "OK"

@dataclass
class SchemaValidator(Validator):
    """Full structure validation — types, nesting, cross-field, $ref composition.

    schema: {"field": {"type": "str", "required": True, "enum": [...],
                       "min_length": N, "min": N, "max": N,
                       "items": {"type": "str"},
                       "properties": {nested schema},
                       "$ref": "address"}}
    defs: {"address": {"street": {"type":"str"}, "city": {"type":"str"}}}
    cross_rules: [lambda data: (True,"") or (False,"error msg")]
    """
    name: str = "SchemaValidator"
    required_fields: List[str] = field(default_factory=list)
    must_contain: List[str] = field(default_factory=list)
    max_length: int = 0
    schema: Dict[str, Dict] = field(default_factory=dict)
    cross_rules: List[Callable] = field(default_factory=list)
    defs: Dict[str, Dict] = field(default_factory=dict)

    _TYPE_MAP = {"str": str, "string": str, "int": int, "integer": int,
                 "float": (int, float), "number": (int, float),
                 "bool": bool, "boolean": bool, "list": list, "dict": dict}

    def validate(self, c):
        if not c or not c.strip(): return False, "Empty"
        errs = []
        if self.max_length and len(c) > self.max_length: errs.append(f">{self.max_length}chars")
        lo = c.lower()
        for kw in self.must_contain:
            if kw.lower() not in lo: errs.append(f"Missing:'{kw}'")
        for f in self.required_fields:
            if f.lower() + ":" not in lo and f.lower() not in lo: errs.append(f"No field:'{f}'")
        if self.schema:
            verrs = self._validate_schema_rich(c)
            errs.extend(str(e) for e in verrs)
        return (True, "OK") if not errs else (False, "; ".join(errs))

    def validate_rich(self, c) -> Tuple[bool, List[ValidationError]]:
        if not c or not c.strip(): return False, [ValidationError(message="Empty")]
        errs: List[ValidationError] = []
        if self.max_length and len(c) > self.max_length:
            errs.append(ValidationError(rule="max_length", message=f">{self.max_length}chars"))
        if self.schema: errs.extend(self._validate_schema_rich(c))
        return (True, []) if not errs else (False, errs)

    def _validate_schema_rich(self, raw: str) -> List[ValidationError]:
        try:
            data = self._extract_json(raw)
            if data is None: return [ValidationError(rule="json_parse", message="Output is not valid JSON")]
        except Exception: return [ValidationError(rule="json_parse", message="Failed to parse JSON")]
        errs = self._check_fields(data, self.schema, "")
        for rule in self.cross_rules:
            try:
                ok, msg = rule(data)
                if not ok: errs.append(ValidationError(rule="cross_field", message=msg))
            except Exception as e: errs.append(ValidationError(rule="cross_field", message=f"Error: {e}"))
        return errs

    def _check_fields(self, data: Dict, schema: Dict, prefix: str) -> List[ValidationError]:
        errs: List[ValidationError] = []
        pfx = f"{prefix}." if prefix else ""
        for fname, rules in schema.items():
            fpath = f"{pfx}{fname}"
            ref = rules.get("$ref")
            if ref and ref in self.defs:
                resolved = {k: v for k, v in rules.items() if k != "$ref"}
                resolved.setdefault("properties", {}).update(self.defs[ref])
                rules = resolved
            required = rules.get("required", True)
            if fname not in data:
                if required: errs.append(ValidationError(field=fname, rule="required", message=f"Missing '{fpath}'", path=prefix))
                continue
            val = data[fname]
            expected = rules.get("type")
            if expected:
                py_type = self._TYPE_MAP.get(expected)
                if py_type and not isinstance(val, py_type):
                    errs.append(ValidationError(field=fname, rule="type", message=f"expected {expected}, got {type(val).__name__}", value=type(val).__name__, path=prefix))
            allowed = rules.get("enum")
            if allowed and val not in allowed:
                errs.append(ValidationError(field=fname, rule="enum", message=f"'{val}' not in {allowed}", value=val, path=prefix))
            ml = rules.get("min_length")
            if ml and hasattr(val, "__len__") and len(val) < ml:
                errs.append(ValidationError(field=fname, rule="min_length", message=f"too short ({len(val)}<{ml})", value=len(val), path=prefix))
            mx = rules.get("max"); mn = rules.get("min")
            if mx is not None and isinstance(val, (int, float)) and val > mx:
                errs.append(ValidationError(field=fname, rule="max", message=f"{val}>{mx}", value=val, path=prefix))
            if mn is not None and isinstance(val, (int, float)) and val < mn:
                errs.append(ValidationError(field=fname, rule="min", message=f"{val}<{mn}", value=val, path=prefix))
            nested = rules.get("properties")
            if nested and isinstance(val, dict):
                errs.extend(self._check_fields(val, nested, fpath))
            items_rule = rules.get("items")
            if items_rule and isinstance(val, list):
                item_type = self._TYPE_MAP.get(items_rule.get("type", ""))
                if item_type:
                    for i, item in enumerate(val):
                        if not isinstance(item, item_type):
                            errs.append(ValidationError(field=f"{fname}[{i}]", rule="item_type", message=f"expected {items_rule['type']}, got {type(item).__name__}", path=prefix))
        return errs

    @staticmethod
    def _extract_json(raw: str):
        raw = raw.strip()
        try: return json.loads(raw)
        except json.JSONDecodeError: pass
        if "```" in raw:
            parts = raw.split("```")
            for p in parts[1::2]:
                p = p.strip()
                if p.startswith("json"): p = p[4:].strip()
                try: return json.loads(p)
                except (ValueError, json.JSONDecodeError): pass
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            try: return json.loads(raw[start:end + 1])
            except (ValueError, json.JSONDecodeError): pass
        return None

class MultiValidator:
    def __init__(self, v=None): self.validators = list(v) if v else [Validator()]
    def validate(self, c):
        f = []
        for v in self.validators:
            ok, r = v.validate(c)
            if not ok:
                if isinstance(r, str): f.append(f"{v.name}: {r}")
                elif isinstance(r, list): f.extend(f"{v.name}: {e}" for e in r)
                else: f.append(str(r))
        return not f, f
    def validate_structured(self, c) -> Tuple[bool, List[ValidationError]]:
        errors = []
        for v in self.validators:
            ok, r = v.validate(c)
            if not ok:
                if isinstance(r, str): errors.append(ValidationError(message=f"{v.name}: {r}"))
                elif isinstance(r, list):
                    for e in r: errors.append(ValidationError(message=f"{v.name}: {e}") if isinstance(e, str) else e)
                else: errors.append(ValidationError(message=str(r)))
        return not errors, errors

# ================================================================
#  Built-in schema presets for common domains
# ================================================================

SCHEMA_PRESETS = {
    "research_report": SchemaValidator(
        schema={
            "title": {"type": "str", "required": True, "min_length": 5},
            "sources": {"type": "list", "required": True, "min_length": 1, "items": {"type": "str"}},
            "findings": {"type": "str", "required": True, "min_length": 20},
            "confidence": {"type": "float", "required": False, "min": 0.0, "max": 1.0},
        },
        defs={"source_entry": {"url": {"type": "str"}, "title": {"type": "str"}, "credibility": {"type": "str", "enum": ["high", "medium", "low"]}}},
    ),
    "prd": SchemaValidator(
        schema={
            "problem": {"type": "str", "required": True, "min_length": 10},
            "solution": {"type": "str", "required": True, "min_length": 10},
            "success_metrics": {"type": "list", "required": True, "min_length": 1, "items": {"type": "str"}},
            "risks": {"type": "list", "required": False, "items": {"type": "str"}},
            "priority": {"type": "str", "required": False, "enum": ["critical", "high", "medium", "low"]},
        },
    ),
    "code_review": SchemaValidator(
        schema={
            "files_reviewed": {"type": "list", "required": True, "items": {"type": "str"}},
            "issues": {"type": "list", "required": True},
            "severity": {"type": "str", "required": True, "enum": ["critical", "major", "minor", "info"]},
            "approved": {"type": "bool", "required": True},
        },
    ),
    "competitor_analysis": SchemaValidator(
        schema={
            "competitors": {"type": "list", "required": True, "min_length": 1},
            "strengths": {"type": "list", "required": True},
            "weaknesses": {"type": "list", "required": True},
            "recommendation": {"type": "str", "required": True, "min_length": 10},
        },
    ),
    "meeting_summary": SchemaValidator(
        schema={
            "attendees": {"type": "list", "required": True, "items": {"type": "str"}},
            "decisions": {"type": "list", "required": True},
            "action_items": {"type": "list", "required": True},
            "next_meeting": {"type": "str", "required": False},
        },
    ),
}
