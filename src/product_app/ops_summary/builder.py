from __future__ import annotations

from pathlib import Path

from src.product_app.agent_runtime import resolve_agent_runtime
from src.product_app.quality_index import build_quality_summary

from .models import OpsSectionStatus, OpsSummary

_DEFAULT_STAGES = (
    "runtime_preflight",
    "codex_pm",
    "codex_architect",
    "claude_lead_plan",
    "claude_developer",
    "claude_tester",
    "claude_lead_review",
    "codex_reviewer",
    "codex_acceptance",
)


def _section(name: str, available: bool, status: str, note: str = "") -> OpsSectionStatus:
    return OpsSectionStatus(name=name, available=available, status=status, note=note)


def _runtime_profiles(stages: tuple[str, ...]) -> list[dict]:
    profiles: list[dict] = []
    for stage in stages:
        profile = resolve_agent_runtime(stage)
        payload = profile.model_dump(mode="json")
        payload.pop("generated_at", None)
        profiles.append(payload)
    return profiles


def _overall_status(sections: list[OpsSectionStatus], warnings: list[str]) -> str:
    if any(section.status == "fail" for section in sections):
        return "fail"
    if warnings or any(section.status == "warn" for section in sections):
        return "warn"
    if all(section.available for section in sections):
        return "pass"
    return "unknown"


def build_ops_summary(
    repo_root: str | Path = ".",
    *,
    stages: tuple[str, ...] = _DEFAULT_STAGES,
) -> OpsSummary:
    """Build a read-only operations summary.

    This function aggregates already-safe summaries. It does not execute stage
    runners, mutate repository files, or expose raw command values.
    """

    root = Path(repo_root).resolve()
    warnings: list[str] = []
    sections: list[OpsSectionStatus] = []

    runtime_profiles = _runtime_profiles(stages)
    runtime_warn = sum(1 for item in runtime_profiles if item.get("mode") in {"unknown", "disabled"})
    sections.append(
        _section(
            "runtime_profiles",
            True,
            "warn" if runtime_warn else "pass",
            f"profiles={len(runtime_profiles)} warn_like={runtime_warn}",
        )
    )

    quality = build_quality_summary(root).model_dump(mode="json")
    quality_total = int(quality.get("total_count") or 0)
    quality_open = int(quality.get("open_count") or 0)
    sections.append(
        _section(
            "quality_summary",
            True,
            "warn" if quality_open else "pass",
            f"total={quality_total} open={quality_open}",
        )
    )

    expected_docs = [
        "docs/roadmap/MASTER_ROADMAP.md",
        "docs/roadmap/README.md",
    ]
    missing_docs = [path for path in expected_docs if not (root / path).exists()]
    if missing_docs:
        warnings.extend(f"missing expected doc: {path}" for path in missing_docs)
    sections.append(
        _section(
            "roadmap_docs",
            not missing_docs,
            "warn" if missing_docs else "pass",
            f"missing={len(missing_docs)}",
        )
    )

    return OpsSummary(
        repo_root=root.as_posix(),
        sections=sections,
        runtime_profiles=runtime_profiles,
        quality_summary=quality,
        overall_status=_overall_status(sections, warnings),
        warnings=warnings,
    )
