"""Tests for validation.py — validators, schema, cross-field rules."""
import json
import pytest
from agent_swarm.validation import (
    Validator, LengthValidator, SchemaValidator, MultiValidator,
    ValidationError, SCHEMA_PRESETS,
)


# ── Base Validator ──

def test_base_validator_ok():
    v = Validator()
    ok, msg = v.validate("hello")
    assert ok is True


def test_base_validator_empty():
    v = Validator()
    ok, msg = v.validate("")
    assert ok is False
    assert "Empty" in msg


def test_base_validator_whitespace():
    v = Validator()
    ok, msg = v.validate("   ")
    assert ok is False


# ── LengthValidator ──

def test_length_validator_ok():
    v = LengthValidator(min_length=3, max_length=10)
    ok, _ = v.validate("hello")
    assert ok is True


def test_length_validator_too_short():
    v = LengthValidator(min_length=10)
    ok, msg = v.validate("hi")
    assert ok is False
    assert "Short" in msg


def test_length_validator_too_long():
    v = LengthValidator(max_length=5)
    ok, msg = v.validate("a" * 100)
    assert ok is False
    assert "Long" in msg


# ── SchemaValidator ──

def test_schema_validator_valid_json():
    v = SchemaValidator(schema={
        "name": {"type": "str", "required": True},
        "age": {"type": "int", "required": True, "min": 0, "max": 150},
    })
    data = json.dumps({"name": "Alice", "age": 30})
    ok, msg = v.validate(data)
    assert ok is True


def test_schema_validator_missing_required():
    v = SchemaValidator(schema={
        "name": {"type": "str", "required": True},
        "email": {"type": "str", "required": True},
    })
    data = json.dumps({"name": "Alice"})
    ok, msg = v.validate(data)
    assert ok is False
    assert "email" in msg.lower()


def test_schema_validator_wrong_type():
    v = SchemaValidator(schema={
        "count": {"type": "int", "required": True},
    })
    data = json.dumps({"count": "not a number"})
    ok, msg = v.validate(data)
    assert ok is False
    assert "type" in msg.lower() or "int" in msg.lower()


def test_schema_validator_enum():
    v = SchemaValidator(schema={
        "status": {"type": "str", "required": True, "enum": ["active", "inactive"]},
    })
    ok1, _ = v.validate(json.dumps({"status": "active"}))
    assert ok1 is True
    ok2, msg = v.validate(json.dumps({"status": "unknown"}))
    assert ok2 is False
    assert "not in" in msg.lower()


def test_schema_validator_min_max():
    v = SchemaValidator(schema={
        "score": {"type": "float", "required": True, "min": 0.0, "max": 1.0},
    })
    ok1, _ = v.validate(json.dumps({"score": 0.5}))
    assert ok1 is True
    ok2, _ = v.validate(json.dumps({"score": 1.5}))
    assert ok2 is False
    ok3, _ = v.validate(json.dumps({"score": -0.1}))
    assert ok3 is False


def test_schema_validator_nested():
    v = SchemaValidator(schema={
        "user": {"type": "dict", "required": True, "properties": {
            "name": {"type": "str", "required": True},
            "role": {"type": "str", "required": True},
        }},
    })
    ok1, _ = v.validate(json.dumps({"user": {"name": "Alice", "role": "admin"}}))
    assert ok1 is True
    ok2, msg = v.validate(json.dumps({"user": {"name": "Alice"}}))
    assert ok2 is False


def test_schema_validator_list_items():
    v = SchemaValidator(schema={
        "tags": {"type": "list", "required": True, "items": {"type": "str"}},
    })
    ok1, _ = v.validate(json.dumps({"tags": ["a", "b", "c"]}))
    assert ok1 is True
    ok2, msg = v.validate(json.dumps({"tags": ["a", 123]}))
    assert ok2 is False


def test_schema_validator_ref():
    v = SchemaValidator(
        schema={"address": {"type": "dict", "required": True, "$ref": "addr"}},
        defs={"addr": {"street": {"type": "str", "required": True}, "city": {"type": "str", "required": True}}},
    )
    ok1, _ = v.validate(json.dumps({"address": {"street": "123 Main", "city": "NY"}}))
    assert ok1 is True
    ok2, _ = v.validate(json.dumps({"address": {"street": "123 Main"}}))
    assert ok2 is False


def test_schema_validator_cross_rules():
    v = SchemaValidator(
        schema={
            "start": {"type": "int", "required": True},
            "end": {"type": "int", "required": True},
        },
        cross_rules=[lambda d: (True, "") if d["end"] > d["start"] else (False, "end must be > start")],
    )
    ok1, _ = v.validate(json.dumps({"start": 1, "end": 10}))
    assert ok1 is True
    ok2, msg = v.validate(json.dumps({"start": 10, "end": 1}))
    assert ok2 is False
    assert "end must be" in msg


def test_schema_validator_must_contain():
    v = SchemaValidator(must_contain=["conclusion", "recommendation"])
    ok1, _ = v.validate("This conclusion and recommendation are clear.")
    assert ok1 is True
    ok2, msg = v.validate("This has no key terms.")
    assert ok2 is False
    assert "Missing" in msg


def test_schema_validator_extract_json_from_markdown():
    v = SchemaValidator(schema={"name": {"type": "str", "required": True}})
    md = '```json\n{"name": "test"}\n```'
    ok, _ = v.validate(md)
    assert ok is True


def test_schema_validator_not_json():
    v = SchemaValidator(schema={"name": {"type": "str", "required": True}})
    ok, msg = v.validate("This is plain text with no JSON")
    assert ok is False


def test_schema_validator_optional_field():
    v = SchemaValidator(schema={
        "name": {"type": "str", "required": True},
        "bio": {"type": "str", "required": False},
    })
    ok, _ = v.validate(json.dumps({"name": "Alice"}))
    assert ok is True


# ── MultiValidator ──

def test_multi_validator_all_pass():
    mv = MultiValidator([Validator(), LengthValidator(min_length=1, max_length=1000)])
    ok, fails = mv.validate("hello world")
    assert ok is True
    assert fails == []


def test_multi_validator_one_fails():
    mv = MultiValidator([Validator(), LengthValidator(min_length=100)])
    ok, fails = mv.validate("short")
    assert ok is False
    assert len(fails) == 1


def test_multi_validator_structured():
    mv = MultiValidator([Validator()])
    ok, errors = mv.validate_structured("valid content")
    assert ok is True
    ok2, errors2 = mv.validate_structured("")
    assert ok2 is False
    assert len(errors2) > 0
    assert isinstance(errors2[0], ValidationError)


# ── Schema Presets ──

def test_preset_research_report():
    v = SCHEMA_PRESETS["research_report"]
    valid = json.dumps({
        "title": "Market Analysis 2026",
        "sources": ["https://example.com"],
        "findings": "The market shows significant growth in AI agents sector.",
        "confidence": 0.85,
    })
    ok, _ = v.validate(valid)
    assert ok is True


def test_preset_code_review():
    v = SCHEMA_PRESETS["code_review"]
    valid = json.dumps({
        "files_reviewed": ["core.py", "tools.py"],
        "issues": ["Missing error handling in line 42"],
        "severity": "major",
        "approved": False,
    })
    ok, _ = v.validate(valid)
    assert ok is True


# ── ValidationError ──

def test_validation_error_str():
    e = ValidationError(field="name", rule="required", message="Missing 'name'", path="user")
    assert "user.name" in str(e)
    assert "Missing" in str(e)


def test_validation_error_no_path():
    e = ValidationError(message="General error")
    assert str(e) == "General error"
