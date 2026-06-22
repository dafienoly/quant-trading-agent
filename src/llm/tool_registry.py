"""DeepSeek 只读工具注册、参数校验和路径安全。"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from src.llm.conversation import sanitize_text


ToolFunc = Callable[..., dict[str, Any]]
_MAX_FILE_LINES = 500
_SAFE_BUG_ID = re.compile(r"^BUG_[A-Za-z0-9_-]+$")


@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    parameters: dict[str, Any]
    func: ToolFunc
    read_only: bool = True


class ToolRegistry:
    """只允许显式注册的只读工具。"""

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        register_defaults: bool = True,
        max_output_bytes: int = 8 * 1024,
    ) -> None:
        self.project_root = Path(project_root or Path(__file__).resolve().parents[2]).resolve()
        self.max_output_bytes = max(64, int(max_output_bytes))
        self._tools: dict[str, ToolDef] = {}
        if register_defaults:
            self._register_defaults()

    def register(self, tool: ToolDef) -> None:
        if tool.name in self._tools:
            raise ValueError(f"工具已注册: {tool.name}")
        if not tool.read_only:
            raise ValueError(f"Only read-only tools may be registered: {tool.name}")
        if tool.parameters.get("type") != "object":
            raise ValueError(f"工具参数 schema 必须是 object: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDef | None:
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        return sorted(self._tools)

    def to_openai_tools(self, names: list[str] | None = None) -> list[dict[str, Any]]:
        selected = names if names is not None else self.list_tools()
        definitions: list[dict[str, Any]] = []
        for name in selected:
            tool = self._tools.get(name)
            if tool is None:
                raise KeyError(name)
            definitions.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
            )
        return definitions

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self._tools.get(name)
        if tool is None:
            return self._result(error="unknown_tool")
        if not tool.read_only:
            return self._result(error="write_tool_not_allowed")
        validation_error = self._validate_arguments(tool.parameters, arguments)
        if validation_error:
            return self._result(error=validation_error)
        try:
            raw = tool.func(**arguments)
        except Exception as exc:
            logger.warning("只读工具执行失败 tool={} error_type={}", name, type(exc).__name__)
            return self._result(error="tool_execution_failed")

        if not isinstance(raw, dict):
            return self._result(error="invalid_tool_result")
        if raw.get("error"):
            return self._result(error=str(raw["error"]))
        return self._result(
            result=str(raw.get("result", "")),
            truncated=bool(raw.get("truncated", False)),
        )

    def _result(
        self,
        *,
        result: str = "",
        error: str | None = None,
        truncated: bool = False,
    ) -> dict[str, Any]:
        sanitized = sanitize_text(result)
        encoded = sanitized.encode("utf-8")
        if len(encoded) > self.max_output_bytes:
            sanitized = encoded[: self.max_output_bytes].decode("utf-8", errors="ignore")
            sanitized += "\n...（已截断）"
            truncated = True
        safe_error = sanitize_text(error) if error else None
        return {"result": sanitized, "error": safe_error, "truncated": truncated}

    @staticmethod
    def _validate_arguments(schema: dict[str, Any], arguments: Any) -> str | None:
        if not isinstance(arguments, dict):
            return "arguments_must_be_object"
        properties = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in arguments:
                return f"missing_argument:{name}"
        if schema.get("additionalProperties") is False:
            unexpected = sorted(set(arguments) - set(properties))
            if unexpected:
                return f"unexpected_argument:{unexpected[0]}"
        python_types = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        for name, value in arguments.items():
            expected_name = properties.get(name, {}).get("type")
            expected = python_types.get(expected_name)
            if expected is None:
                continue
            valid = isinstance(value, expected)
            if expected_name in {"integer", "number"} and isinstance(value, bool):
                valid = False
            if not valid:
                return f"invalid_argument_type:{name}"
        return None

    def _register_defaults(self) -> None:
        self.register(
            ToolDef(
                name="read_project_file",
                description="读取项目允许目录内的 UTF-8 文本文件片段。",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "max_lines": {"type": "integer", "default": 200},
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
                func=self._read_project_file,
            )
        )
        self.register(
            ToolDef(
                name="search_project_text",
                description="在项目允许目录内使用固定 ripgrep 命令搜索文本。",
                parameters={
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string"},
                        "directory": {"type": "string", "default": "src"},
                        "max_results": {"type": "integer", "default": 10},
                    },
                    "required": ["pattern"],
                    "additionalProperties": False,
                },
                func=self._search_project_text,
            )
        )
        self.register(
            ToolDef(
                name="list_feedback_bugs",
                description="列出 feedback/bugs/open 下的 Bug JSON 文件。",
                parameters={
                    "type": "object",
                    "properties": {"max_results": {"type": "integer", "default": 20}},
                    "additionalProperties": False,
                },
                func=self._list_feedback_bugs,
            )
        )
        self.register(
            ToolDef(
                name="read_feedback_bug",
                description="读取一个 open Bug JSON，并截断 traceback。",
                parameters={
                    "type": "object",
                    "properties": {"bug_id": {"type": "string"}},
                    "required": ["bug_id"],
                    "additionalProperties": False,
                },
                func=self._read_feedback_bug,
            )
        )
        for name, directory, description in (
            ("read_test_report", "docs/test_reports", "读取测试报告。"),
            ("read_dev_report", "docs/dev_reports", "读取开发报告。"),
        ):
            self.register(
                ToolDef(
                    name=name,
                    description=description,
                    parameters={
                        "type": "object",
                        "properties": {
                            "filename": {"type": "string"},
                            "max_lines": {"type": "integer", "default": 200},
                        },
                        "required": ["filename"],
                        "additionalProperties": False,
                    },
                    func=lambda filename, max_lines=200, directory=directory: self._read_doc_file(
                        directory, filename, max_lines
                    ),
                )
            )

    def _read_project_file(self, path: str, max_lines: int = 200) -> dict[str, Any]:
        resolved = self._resolve_allowed(path)
        if resolved is None:
            return {"error": "access_denied"}
        return self._read_text_file(resolved, max_lines)

    def _search_project_text(
        self,
        pattern: str,
        directory: str = "src",
        max_results: int = 10,
    ) -> dict[str, Any]:
        if not pattern or len(pattern) > 300:
            return {"error": "invalid_search_pattern"}
        resolved = self._resolve_allowed(directory)
        if resolved is None or not resolved.is_dir():
            return {"error": "access_denied"}
        limit = min(max(1, max_results), 30)
        try:
            relative_directory = resolved.relative_to(self.project_root)
            completed = subprocess.run(
                [
                    "rg",
                    "-n",
                    "--no-heading",
                    "--color",
                    "never",
                    "--",
                    pattern,
                    str(relative_directory),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=15,
                check=False,
                cwd=self.project_root,
            )
        except FileNotFoundError:
            return {"error": "ripgrep_not_available"}
        except subprocess.TimeoutExpired:
            return {"error": "search_timeout"}
        if completed.returncode not in {0, 1}:
            return {"error": "search_failed"}
        lines = completed.stdout.splitlines()
        return {
            "result": "\n".join(lines[:limit]),
            "truncated": len(lines) > limit,
        }

    def _list_feedback_bugs(self, max_results: int = 20) -> dict[str, Any]:
        directory = self.project_root / "feedback" / "bugs" / "open"
        if not directory.is_dir():
            return {"result": "未发现 open Bug。"}
        limit = min(max(1, max_results), 50)
        files = sorted(path.name for path in directory.glob("BUG_*.json"))[:limit]
        return {"result": "\n".join(files) if files else "未发现 open Bug。"}

    def _read_feedback_bug(self, bug_id: str) -> dict[str, Any]:
        if not _SAFE_BUG_ID.fullmatch(bug_id):
            return {"error": "invalid_bug_id"}
        path = self.project_root / "feedback" / "bugs" / "open" / f"{bug_id}.json"
        if not path.is_file():
            return {"error": "bug_not_found"}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"error": "bug_read_failed"}
        if isinstance(payload, dict) and isinstance(payload.get("sanitized_traceback"), str):
            payload["sanitized_traceback"] = payload["sanitized_traceback"][:500]
        return {"result": json.dumps(payload, ensure_ascii=False, indent=2)}

    def _read_doc_file(self, directory: str, filename: str, max_lines: int) -> dict[str, Any]:
        if Path(filename).name != filename:
            return {"error": "access_denied"}
        resolved = self._resolve_allowed(f"{directory}/{filename}")
        if resolved is None:
            return {"error": "access_denied"}
        return self._read_text_file(resolved, max_lines)

    @staticmethod
    def _read_text_file(path: Path, max_lines: int) -> dict[str, Any]:
        if not path.is_file():
            return {"error": "file_not_found"}
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            return {"error": "file_read_failed"}
        limit = min(max(1, max_lines), _MAX_FILE_LINES)
        return {"result": "\n".join(lines[:limit]), "truncated": len(lines) > limit}

    def _resolve_allowed(self, relative_path: str) -> Path | None:
        candidate = Path(relative_path)
        if candidate.is_absolute():
            return None
        resolved = (self.project_root / candidate).resolve()
        allowed_roots = [
            self.project_root / name for name in ("src", "docs", "tests", "feedback", "scripts")
        ]
        if not any(self._is_within(resolved, root.resolve()) for root in allowed_roots):
            return None
        forbidden_parts = {".git", ".venv", "runtime", "logs", "__pycache__"}
        relative_parts = resolved.relative_to(self.project_root).parts
        if any(part in forbidden_parts or part.startswith(".env") for part in relative_parts):
            return None
        if resolved.suffix.lower() in {".pem", ".key", ".p12"}:
            return None
        return resolved

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False


_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
