from __future__ import annotations

import json

import pytest

from src.llm.tool_registry import ToolDef, ToolRegistry


def test_write_tool_registration_is_rejected():
    registry = ToolRegistry(register_defaults=False)

    with pytest.raises(ValueError, match="read-only"):
        registry.register(
            ToolDef(
                name="write_file",
                description="write",
                parameters={"type": "object", "properties": {}},
                func=lambda: {"result": "written"},
                read_only=False,
            )
        )


def test_unknown_tool_schema_is_rejected():
    registry = ToolRegistry(register_defaults=False)

    with pytest.raises(KeyError):
        registry.to_openai_tools(["missing"])


def test_argument_schema_rejects_missing_wrong_and_extra_fields():
    registry = ToolRegistry(register_defaults=False)
    registry.register(
        ToolDef(
            name="read_note",
            description="read",
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string"}, "limit": {"type": "integer"}},
                "required": ["name"],
                "additionalProperties": False,
            },
            func=lambda name, limit=1: {"result": name * limit},
        )
    )

    assert registry.execute("read_note", {})["error"] == "missing_argument:name"
    assert registry.execute("read_note", {"name": 1})["error"] == "invalid_argument_type:name"
    assert registry.execute("read_note", {"name": "x", "extra": True})["error"] == (
        "unexpected_argument:extra"
    )


def test_tool_output_is_truncated_and_redacted():
    registry = ToolRegistry(register_defaults=False, max_output_bytes=64)
    registry.register(
        ToolDef(
            name="read_note",
            description="read",
            parameters={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            func=lambda: {"result": "token=TEST_OUTPUT_VALUE " + "x" * 200},
        )
    )

    result = registry.execute("read_note", {})

    assert result["error"] is None
    assert result["truncated"] is True
    assert "TEST_OUTPUT_VALUE" not in result["result"]


def test_tool_error_text_is_redacted():
    registry = ToolRegistry(register_defaults=False)
    registry.register(
        ToolDef(
            name="read_note",
            description="read",
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            func=lambda: {"error": "token=TEST_ERROR_VALUE"},
        )
    )

    result = registry.execute("read_note", {})

    assert "TEST_ERROR_VALUE" not in result["error"]
    assert "REDACTED" in result["error"]


def test_default_file_tool_allows_safe_file_and_rejects_escape(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "safe.py").write_text("print('safe')", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=TEST_VALUE", encoding="utf-8")
    registry = ToolRegistry(project_root=tmp_path)

    safe = registry.execute("read_project_file", {"path": "src/safe.py"})
    escaped = registry.execute("read_project_file", {"path": "../outside.txt"})
    env_file = registry.execute("read_project_file", {"path": ".env"})

    assert "print('safe')" in safe["result"]
    assert escaped["error"] == "access_denied"
    assert env_file["error"] == "access_denied"


def test_default_tools_are_read_only_and_openai_compatible(tmp_path):
    registry = ToolRegistry(project_root=tmp_path)

    for name in registry.list_tools():
        tool = registry.get(name)
        assert tool is not None
        assert tool.read_only is True

    definitions = registry.to_openai_tools(["read_project_file"])
    assert definitions[0]["type"] == "function"
    assert definitions[0]["function"]["name"] == "read_project_file"
    json.dumps(definitions)
