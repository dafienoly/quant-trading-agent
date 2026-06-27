from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .models import QualityItem, QualityPriority, QualityState, QualitySummary

_SCAN_ROOTS = (
    "feedback/bugs/open",
    "feedback/bugs/resolved",
)
_ALLOWED_SUFFIXES = {".json", ".md", ".yaml", ".yml"}
_TEXT_LIMIT = 220


def _repo_relative(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return ""


def _safe_root(repo_root: Path, relative_root: str) -> Path:
    root = (repo_root / relative_root).resolve()
    if not str(root).startswith(str(repo_root.resolve())):
        raise ValueError("scan root must stay inside repository")
    return root


def _normal_state(raw: str, fallback: QualityState) -> QualityState:
    value = str(raw or "").strip().lower()
    if value in {"open", "opened", "new"}:
        return QualityState.OPEN
    if value in {"resolved", "closed", "done", "fixed"}:
        return QualityState.RESOLVED
    if value in {"invalid", "ignored", "not_planned"}:
        return QualityState.INVALID
    return fallback


def _normal_priority(raw: str) -> QualityPriority:
    value = str(raw or "").strip().lower()
    mapping = {
        "p0": QualityPriority.P0,
        "critical": QualityPriority.P0,
        "p1": QualityPriority.P1,
        "high": QualityPriority.P1,
        "p2": QualityPriority.P2,
        "medium": QualityPriority.P2,
        "p3": QualityPriority.P3,
        "low": QualityPriority.P3,
    }
    return mapping.get(value, QualityPriority.UNKNOWN)


def _safe_text(value: object) -> str:
    text = str(value or "").replace("\x00", "").strip()
    text = " ".join(text.split())
    return text[:_TEXT_LIMIT]


def _parse_markdown(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    lines = text.splitlines()
    for line in lines[:80]:
        stripped = line.strip().strip("-")
        if not stripped:
            continue
        if stripped.startswith("#") and not data.get("title"):
            data["title"] = stripped.lstrip("#").strip()
            continue
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            value = value.strip()
            if key in {
                "id",
                "feedback_id",
                "state",
                "status",
                "priority",
                "severity",
                "source_stage",
                "route_back_to",
                "title",
                "summary",
                "created_at",
                "resolved_at",
            }:
                data[key] = value
    if not data.get("summary"):
        data["summary"] = "\n".join(lines[:8])
    return data


def _load_payload(path: Path) -> tuple[dict[str, Any], list[str]]:
    notes: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return {}, ["unreadable"]

    if path.suffix == ".json":
        try:
            loaded = json.loads(text)
            if isinstance(loaded, dict):
                return loaded, notes
            return {}, ["json root is not object"]
        except ValueError:
            return {}, ["invalid json"]

    if path.suffix in {".yaml", ".yml"}:
        try:
            loaded = yaml.safe_load(text)
            if isinstance(loaded, dict):
                return loaded, notes
            return {}, ["yaml root is not object"]
        except yaml.YAMLError:
            return {}, ["invalid yaml"]

    return _parse_markdown(text), notes


def _fallback_state_from_path(path: Path) -> QualityState:
    parts = set(path.parts)
    if "open" in parts:
        return QualityState.OPEN
    if "resolved" in parts:
        return QualityState.RESOLVED
    return QualityState.UNKNOWN


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [_safe_text(item) for item in value if str(item or "").strip()]
    if isinstance(value, str) and value.strip():
        return [_safe_text(value)]
    return []


def _build_item(path: Path, repo_root: Path) -> QualityItem:
    payload, notes = _load_payload(path)
    rel = _repo_relative(path, repo_root)
    fallback_state = _fallback_state_from_path(path)
    state = _normal_state(
        str(payload.get("state") or payload.get("status") or ""),
        fallback_state,
    )
    priority = _normal_priority(str(payload.get("priority") or payload.get("severity") or ""))
    item_id = _safe_text(payload.get("feedback_id") or payload.get("id") or path.stem)
    if notes and state == QualityState.UNKNOWN:
        state = QualityState.INVALID

    return QualityItem(
        item_id=item_id,
        state=state,
        priority=priority,
        source_stage=_safe_text(payload.get("source_stage")),
        route_back_to=_safe_text(payload.get("route_back_to")),
        related_paths=_string_list(payload.get("evidence_paths") or payload.get("related_paths")),
        item_path=rel,
        title=_safe_text(payload.get("title") or item_id),
        safe_summary=_safe_text(payload.get("summary") or payload.get("safe_summary")),
        created_at=_safe_text(payload.get("created_at")),
        resolved_at=_safe_text(payload.get("resolved_at")),
        parse_notes=notes,
    )


def _iter_quality_files(repo_root: Path) -> tuple[list[Path], list[str], list[str]]:
    files: list[Path] = []
    warnings: list[str] = []
    roots: list[str] = []
    for relative_root in _SCAN_ROOTS:
        root = _safe_root(repo_root, relative_root)
        roots.append(relative_root)
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix not in _ALLOWED_SUFFIXES:
                warnings.append(f"skipped unsupported file: {_repo_relative(path, repo_root)}")
                continue
            files.append(path)
    return files, roots, warnings


def build_quality_summary(repo_root: str | Path = ".") -> QualitySummary:
    root = Path(repo_root).resolve()
    files, roots, warnings = _iter_quality_files(root)
    items = [_build_item(path, root) for path in files]

    state_counts: dict[str, int] = {}
    priority_counts: dict[str, int] = {}
    for item in items:
        state_counts[item.state.value] = state_counts.get(item.state.value, 0) + 1
        priority_counts[item.priority.value] = priority_counts.get(item.priority.value, 0) + 1

    return QualitySummary(
        scanned_roots=roots,
        total_count=len(items),
        open_count=state_counts.get(QualityState.OPEN.value, 0),
        resolved_count=state_counts.get(QualityState.RESOLVED.value, 0),
        invalid_count=state_counts.get(QualityState.INVALID.value, 0),
        priority_counts=priority_counts,
        state_counts=state_counts,
        items=items,
        warnings=warnings,
    )
