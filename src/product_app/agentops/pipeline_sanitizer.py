from __future__ import annotations

import re

# Match common token patterns: sk-*, ghp_*, gh_*, xoxp-*, xoxb-*
_TOKEN_PATTERN = re.compile(
    r"\b(sk-[A-Za-z0-9_-]{10,}|gh[pous]_[A-Za-z0-9_-]{20,}|xox[bpos]-[A-Za-z0-9_-]{10,})\b"
)
# Match env-var-like assignments: KEY=value where value is non-empty
_ENV_VAR_PATTERN = re.compile(r"([A-Z_]{3,})=([^\s]{4,})")
# Match traceback file lines
_TRACEBACK_PATTERN = re.compile(r'\s*File\s+".*?",\s*line\s+\d+,')
_WINDOWS_ABSOLUTE_PATH_PATTERN = re.compile(r"\b[A-Za-z]:\\[^\s]+")


def sanitize_repo_relative_path(path: str | None) -> str:
    if not path:
        return ""
    path_str = str(path).strip()
    if path_str == ".env":
        return "<redacted>"
    if path_str == ".env.example":
        return ".env.example"
    # Normalize backslashes for cross-platform matching
    normalized = path_str.replace("\\", "/")
    # Try known workspace roots (most specific first)
    for prefix in [
        "/mnt/d/actions-runner/_work/quant-trading-agent/quant-trading-agent/",
        "/mnt/d/actions-runner/_work/quant-trading-agent/",
    ]:
        if normalized.lower().startswith(prefix.lower()):
            return normalized[len(prefix) :]
    # Find occurrence of known repository markers
    for marker in ["quant-trading-agent/", "actions-runner/_work/"]:
        idx = normalized.find(marker)
        if idx != -1:
            return normalized[idx + len(marker) :]
    # General absolute path: find first content-bearing subdirectory
    content_dirs = {"docs", "src", ".agent", "tests", "config", "scripts", "data", "feedback", ".github"}
    parts = normalized.split("/")
    for i, part in enumerate(parts):
        if part in content_dirs and i > 0:
            return "/".join(parts[i:])
    # If it looks like an absolute path (starts with / or drive letter), hide it
    if normalized.startswith("/") or (len(normalized) > 1 and normalized[1] == ":"):
        return "<path>"
    return normalized


def redact_secrets(text: str) -> str:
    result = _TOKEN_PATTERN.sub("<redacted>", text)
    result = _ENV_VAR_PATTERN.sub(r"\1=<redacted>", result)
    return result


def sanitize_error_message(message: str) -> str:
    if not message:
        return ""
    lines = message.split("\n")
    sanitized: list[str] = []
    for line in lines:
        if _TRACEBACK_PATTERN.match(line):
            sanitized.append("<traceback omitted>")
            continue
        line = redact_secrets(line)
        line = _WINDOWS_ABSOLUTE_PATH_PATTERN.sub("<path>", line)
        # Redact absolute path segments (Unix /path and Windows X:\path)
        line = re.sub(
            r"(?:/[a-zA-Z0-9_.\-]+)+(?=[\s]|$)",
            lambda m: sanitize_repo_relative_path(m.group()),
            line,
        )
        sanitized.append(line)
    result = "\n".join(sanitized)
    return result
