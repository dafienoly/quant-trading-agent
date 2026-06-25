from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .pipeline_contracts import DocumentStatus, ErrorInfo
from .pipeline_errors import (
    PipelineStateUnavailableError,
    PipelineStateUnparsableError,
)

STATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "..",
    ".agent",
)


@dataclass
class ResolvedTarget:
    feature_id: str | None = None
    issue_number: int | None = None

    @property
    def invalid(self) -> bool:
        return self.feature_id is None and self.issue_number is None


def resolve_target(
    feature_id: str | None = None, issue_number: int | None = None
) -> ResolvedTarget:
    return ResolvedTarget(feature_id=feature_id, issue_number=issue_number)


@dataclass
class PipelineReadResult:
    state: dict[str, Any]
    not_found: bool = False
    unparsable: bool = False
    partial: bool = False
    errors: list[ErrorInfo] = field(default_factory=list)


def _try_parse_json(content: str) -> dict[str, Any] | None:
    try:
        return json.loads(content)
    except ValueError:
        return None


def _try_parse_yaml(content: str) -> dict[str, Any] | None:
    try:
        data = yaml.safe_load(content)
        if isinstance(data, dict):
            return data
        return {}
    except yaml.YAMLError:
        return None


def _try_parse(content: str) -> dict[str, Any] | None:
    result = _try_parse_json(content)
    if result is not None:
        return result
    return _try_parse_yaml(content)


def read_pipeline_state(
    filepath: str, required: bool = True
) -> PipelineReadResult:
    path = Path(filepath)
    if not path.exists():
        if required:
            raise PipelineStateUnavailableError(filepath)
        return PipelineReadResult({}, not_found=True)

    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        if required:
            raise PipelineStateUnavailableError(filepath)
        return PipelineReadResult({}, not_found=True)

    parsed = _try_parse(content)
    if parsed is None:
        # Try partial parse
        partial_data = _try_parse(content + "\n")
        if partial_data is None:
            if required:
                raise PipelineStateUnparsableError(filepath)
            return PipelineReadResult({}, unparsable=True, partial=True)
        return PipelineReadResult(partial_data, unparsable=True, partial=True)

    return PipelineReadResult(parsed)


def read_handoff_files(handoff_dir: str) -> list[str]:
    path = Path(handoff_dir)
    if not path.is_dir():
        return []
    return sorted(
        str(p) for p in path.iterdir() if p.is_file() and p.suffix == ".md"
    )


def check_doc_status_readonly(path: str) -> DocumentStatus:
    if not path:
        return DocumentStatus.UNKNOWN
    p = Path(path)
    if not p.exists():
        return DocumentStatus.MISSING
    if not os.access(str(p), os.R_OK):
        return DocumentStatus.UNREADABLE
    return DocumentStatus.PRESENT
