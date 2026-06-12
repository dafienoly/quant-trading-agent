"""Tool Registry — register, validate, and execute read-only tools for DeepSeek.

Only **read-only** tools may be registered by default. Any tool that writes
files, executes arbitrary shell commands, or touches trading/risk modules is
forbidden at the registry level.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable

from loguru import logger

# Maximum bytes returned by any tool execution
_MAX_TOOL_OUTPUT_BYTES = 8 * 1024  # 8 KB

# Maximum lines read from a file
_MAX_FILE_LINES = 200

# Project root detection
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Paths that tools are allowed to read
_ALLOWED_READ_PREFIXES = (
    str(_PROJECT_ROOT / "src"),
    str(_PROJECT_ROOT / "docs"),
    str(_PROJECT_ROOT / "tests"),
    str(_PROJECT_ROOT / "feedback"),
    str(_PROJECT_ROOT / "scripts"),
)

# Explicitly forbidden paths (even within allowed prefixes)
_FORBIDDEN_PATTERNS = (
    ".env",
    "runtime/",
    "logs/",
    "__pycache__",
    ".git/",
    ".venv/",
)


# ============================================================
# Tool function type
# ============================================================

ToolFunc = Callable[..., dict[str, Any]]


# ============================================================
# Tool definition
# ============================================================


class ToolDef:
    """Descriptor for a single tool."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        func: ToolFunc,
        read_only: bool = True,
    ) -> None:
        self.name = name
        self.description = description
        self.parameters = parameters
        self.func = func
        self.read_only = read_only


# ============================================================
# Registry
# ============================================================


class ToolRegistry:
    """Central registry for DeepSeek-compatible tools.

    Tools are registered by name and converted to OpenAI-compatible schema
    for inclusion in ``chat.completions.create(tools=[...])``.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDef] = {}
        self._register_defaults()

    def register(self, tool: ToolDef) -> None:
        """Register a tool. Raises ``ValueError`` if name already exists."""
        if tool.name in self._tools:
            raise ValueError(f"Tool {tool.name!r} is already registered")
        if not tool.read_only:
            raise ValueError(f"Only read-only tools are allowed by default: {tool.name!r}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDef | None:
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        return sorted(self._tools)

    def to_openai_tools(self, tool_names: list[str] | None = None) -> list[dict[str, Any]]:
        """Convert registered tools to OpenAI-compatible tool definitions.

        If ``tool_names`` is provided, only those tools are included; otherwise
        all registered tools are returned.
        """
        names = tool_names or self.list_tools()
        result: list[dict[str, Any]] = []
        for name in names:
            tool = self._tools.get(name)
            if tool is None:
                continue
            result.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            })
        return result

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool by name with validated arguments.

        Returns a dict with keys ``result`` (str) and ``error`` (str | None).
        """
        tool = self._tools.get(name)
        if tool is None:
            return {"result": "", "error": f"Unknown tool: {name!r}"}
        if not tool.read_only:
            return {"result": "", "error": f"Write tool not allowed: {name!r}"}
        try:
            output = tool.func(**arguments)
            return _truncate_output(output)
        except Exception as exc:
            logger.warning("Tool {} failed: {}", name, exc)
            return {"result": "", "error": f"{type(exc).__name__}: {exc}"}

    # ------------------------------------------------------------------
    # Default tool implementations
    # ------------------------------------------------------------------

    def _register_defaults(self) -> None:
        self._tools["read_project_file"] = ToolDef(
            name="read_project_file",
            description="Read a file from the project. Path must be relative to project root.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path within the project (e.g. src/api/routes.py)",
                    },
                    "max_lines": {
                        "type": "integer",
                        "description": "Maximum lines to read (default 200, max 500)",
                        "default": 200,
                    },
                },
                "required": ["path"],
            },
            func=_read_project_file,
            read_only=True,
        )
        self._tools["search_project_text"] = ToolDef(
            name="search_project_text",
            description="Search for text in project source code using ripgrep.",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Search pattern (Python regex)",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default 10, max 30)",
                        "default": 10,
                    },
                    "directory": {
                        "type": "string",
                        "description": "Subdirectory to search (default: src/)",
                        "default": "src/",
                    },
                },
                "required": ["pattern"],
            },
            func=_search_project_text,
            read_only=True,
        )
        self._tools["list_feedback_bugs"] = ToolDef(
            name="list_feedback_bugs",
            description="List open Bug feedback files from feedback/bugs/open/",
            parameters={
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of bugs to list (default 20)",
                        "default": 20,
                    },
                },
                "required": [],
            },
            func=_list_feedback_bugs,
            read_only=True,
        )
        self._tools["read_feedback_bug"] = ToolDef(
            name="read_feedback_bug",
            description="Read a single feedback bug file by ID (e.g. BUG_20260610_ABC123)",
            parameters={
                "type": "object",
                "properties": {
                    "bug_id": {
                        "type": "string",
                        "description": "Bug ID like BUG_20260610_ABC123",
                    },
                },
                "required": ["bug_id"],
            },
            func=_read_feedback_bug,
            read_only=True,
        )
        self._tools["read_test_report"] = ToolDef(
            name="read_test_report",
            description="Read a test report from docs/test_reports/",
            parameters={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Filename like 2026-06-12-feature-test-report.md",
                    },
                    "max_lines": {
                        "type": "integer",
                        "description": "Maximum lines (default 200)",
                        "default": 200,
                    },
                },
                "required": ["filename"],
            },
            func=_read_test_report,
            read_only=True,
        )
        self._tools["read_dev_report"] = ToolDef(
            name="read_dev_report",
            description="Read a development report from docs/dev_reports/",
            parameters={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Filename like 2026-06-12-feature-dev-report.md",
                    },
                    "max_lines": {
                        "type": "integer",
                        "description": "Maximum lines (default 200)",
                        "default": 200,
                    },
                },
                "required": ["filename"],
            },
            func=_read_dev_report,
            read_only=True,
        )


# ============================================================
# Default tool implementations
# ============================================================


def _read_project_file(path: str, max_lines: int = 200) -> dict[str, Any]:
    """Read a project file with path validation."""
    full_path = (_PROJECT_ROOT / path).resolve()
    if not _is_path_allowed(full_path):
        return {"result": f"Access denied: {path}", "truncated": False}
    if not full_path.exists():
        return {"result": f"File not found: {path}", "truncated": False}
    if full_path.is_dir():
        return {"result": f"Path is a directory: {path}", "truncated": False}

    try:
        lines = full_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        return {"result": f"Read error: {exc}", "truncated": False}

    max_l = min(max_lines, _MAX_FILE_LINES)
    content = "\n".join(lines[:max_l])
    truncated = len(lines) > max_l
    if truncated:
        content += f"\n... (showing {max_l} of {len(lines)} lines)"
    return {"result": content, "truncated": truncated}


def _search_project_text(pattern: str, max_results: int = 10, directory: str = "src/") -> dict[str, Any]:
    """Search project text using ripgrep."""
    search_path = _PROJECT_ROOT / directory
    if not search_path.exists():
        return {"result": f"Directory not found: {directory}", "truncated": False}

    try:
        result = subprocess.run(
            ["rg", "-n", "--no-heading", pattern, str(search_path)],
            capture_output=True, text=True, timeout=15, encoding="utf-8",
        )
    except FileNotFoundError:
        return {"result": "rg (ripgrep) not found on this system", "truncated": False}
    except subprocess.TimeoutExpired:
        return {"result": "Search timed out", "truncated": False}

    lines = result.stdout.splitlines()
    max_r = min(max_results, 30)
    content = "\n".join(lines[:max_r])
    truncated = len(lines) > max_r
    if truncated:
        content += f"\n... (showing {max_r} of {len(lines)} results)"
    return {"result": content, "truncated": truncated}


def _list_feedback_bugs(max_results: int = 20) -> dict[str, Any]:
    """List bug files from feedback/bugs/open/."""
    bugs_dir = _PROJECT_ROOT / "feedback" / "bugs" / "open"
    if not bugs_dir.exists():
        return {"result": "No feedback/bugs/open/ directory", "truncated": False}
    files = sorted(bugs_dir.glob("*.json"))[:max_results]
    if not files:
        return {"result": "No open bugs found", "truncated": False}
    content = "\n".join(f.name for f in files)
    return {"result": content, "truncated": False}


def _read_feedback_bug(bug_id: str) -> dict[str, Any]:
    """Read a single bug file by ID."""
    for subdir in ("open", "triaged", "fixed", "ignored"):
        path = _PROJECT_ROOT / "feedback" / "bugs" / subdir / f"{bug_id}.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                return {"result": f"Read error: {exc}", "truncated": False}
            # Sanitize: remove stack traces and excessive traceback
            if "sanitized_traceback" in data:
                data["sanitized_traceback"] = data["sanitized_traceback"][:500]
            return {
                "result": json.dumps(data, ensure_ascii=False, indent=2),
                "truncated": False,
            }
    return {"result": f"Bug not found: {bug_id}", "truncated": False}


def _read_test_report(filename: str, max_lines: int = 200) -> dict[str, Any]:
    """Read a test report file."""
    return _read_doc_file("docs/test_reports", filename, max_lines)


def _read_dev_report(filename: str, max_lines: int = 200) -> dict[str, Any]:
    """Read a development report file."""
    return _read_doc_file("docs/dev_reports", filename, max_lines)


# ============================================================
# Shared helpers
# ============================================================


def _read_doc_file(subdir: str, filename: str, max_lines: int) -> dict[str, Any]:
    """Read a file from a docs subdirectory."""
    full_path = (_PROJECT_ROOT / subdir / filename).resolve()
    if not _is_path_allowed(full_path):
        return {"result": f"Access denied: {filename}", "truncated": False}
    if not full_path.exists():
        return {"result": f"File not found: {subdir}/{filename}", "truncated": False}
    if full_path.is_dir():
        return {"result": f"Path is a directory: {filename}", "truncated": False}
    try:
        lines = full_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        return {"result": f"Read error: {exc}", "truncated": False}
    max_l = min(max_lines, _MAX_FILE_LINES)
    content = "\n".join(lines[:max_l])
    truncated = len(lines) > max_l
    if truncated:
        content += f"\n... (showing {max_l} of {len(lines)} lines)"
    return {"result": content, "truncated": truncated}


def _is_path_allowed(full_path: Path) -> bool:
    """Check that a path is within allowed read prefixes and not forbidden."""
    resolved = full_path.resolve()
    for prefix in _ALLOWED_READ_PREFIXES:
        try:
            resolved.relative_to(Path(prefix).resolve())
        except ValueError:
            continue
        # Check forbidden patterns
        path_str = str(resolved)
        if any(pat in path_str for pat in _FORBIDDEN_PATTERNS):
            return False
        return True
    return False


def _truncate_output(output: dict[str, Any]) -> dict[str, Any]:
    """Ensure tool output doesn't exceed byte limit."""
    raw = output.get("result", "")
    if isinstance(raw, str) and len(raw.encode("utf-8")) > _MAX_TOOL_OUTPUT_BYTES:
        truncated_bytes = raw.encode("utf-8")[:_MAX_TOOL_OUTPUT_BYTES]
        output["result"] = truncated_bytes.decode("utf-8", errors="replace") + "\n... (truncated)"
        output["truncated"] = True
    return output


# ============================================================
# Module-level singleton
# ============================================================

_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
