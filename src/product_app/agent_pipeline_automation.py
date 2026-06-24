"""Issue-driven Agent pipeline helpers.

This module is intentionally deterministic. It does not call an LLM or modify
GitHub by itself; GitHub Actions and external Agent commands use it to create
state, handoff prompts, and safety gates.

Safety invariants:
- Trading-sensitive paths are never eligible for unattended main merge.
- Gate checks are file/report based and fail closed when state is missing.
- Agent handoff state is written to repository files for auditability.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

PIPELINE_ROOT = Path(".agent")
STATE_PATH = PIPELINE_ROOT / "state.json"
CURRENT_TASK_PATH = PIPELINE_ROOT / "current_task.yaml"
AUTO_MERGE_GATE_PATH = PIPELINE_ROOT / "gates" / "auto_merge_gate.json"

RESTRICTED_PATH_PREFIXES: tuple[str, ...] = (
    "src/risk_engine/",
    "src/execution_engine/",
    "src/broker/",
    "src/order/",
    "src/account/",
    "src/live_trading/",
    "src/strategy_engine/live",
    "src/strategy_engine/live_",
    "integrations/miniqmt/",
    "src/data_gateway/miniqmt",
    "src/data_gateway/providers/miniqmt",
    "docs/policy/RISK_POLICY.md",
    "docs/policy/EXECUTION_POLICY.md",
    "docs/policy/SELF_TEST_CHECKLIST.md",
    ".env",
    ".env.",
)

RESTRICTED_PATH_CONTAINS: tuple[str, ...] = (
    "miniqmt",
    "xtquant",
    "broker",
    "order_checker",
    "execution_service",
    "trade_recorder",
    "risk_engine",
    "account",
    "credential",
    "secret",
)

SAFE_AUTO_MAIN_PREFIXES: tuple[str, ...] = (
    "docs/",
    "tests/",
    ".github/ISSUE_TEMPLATE/",
    ".agent/",
)

REPORT_GLOBS_BY_STAGE: dict[str, list[str]] = {
    "pm": ["docs/requirements/*-{feature_id}-requirements.md"],
    "architecture": ["docs/design/*-{feature_id}-architecture.md"],
    "team_plan": ["docs/dev_plans/*-{feature_id}*team-plan.md"],
    "phase_dev": ["docs/dev_reports/*-{feature_id}*phase-*dev-report.md"],
    "phase_test": ["docs/test_reports/*-{feature_id}*phase-*test-report.md"],
    "claude_lead_review": [
        "docs/review/*-{feature_id}*opencode-lead-review.md",
        "docs/review/*-{feature_id}*claude-lead-review.md",
    ],
    "codex_review": ["docs/review/*-{feature_id}*codex-review*.md"],
    "acceptance": ["docs/acceptance/*-{feature_id}*acceptance.md"],
}

STAGE_ORDER: tuple[str, ...] = (
    "pm",
    "architecture",
    "team_plan",
    "phase_dev",
    "phase_test",
    "claude_lead_review",
    "codex_review",
    "acceptance",
)

LEGACY_STAGE_ALIASES: dict[str, str] = {
    "dev": "phase_dev",
    "test": "phase_test",
    "review": "codex_review",
}

TEAM_HANDOFF_STAGES: tuple[str, ...] = (
    "codex_pm",
    "codex_architect",
    "claude_lead_plan",
    "claude_developer",
    "claude_tester",
    "claude_lead_review",
    "codex_reviewer",
    "codex_acceptance",
    "bugfix",
    "postmortem",
)


@dataclass(frozen=True)
class PipelineFeature:
    """Metadata for one issue-driven feature pipeline."""

    feature_id: str
    title: str
    risk_level: str
    issue_number: int | None = None
    issue_url: str | None = None
    run_id: str | None = None
    epic_branch: str | None = None
    current_stage: str = "pm_pending"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def with_default_branch(self) -> "PipelineFeature":
        if self.issue_number is not None:
            branch_suffix = f"issue-{self.issue_number}"
        elif self.run_id:
            branch_suffix = f"run-{self.run_id}"
        else:
            branch_suffix = "manual"
        branch = self.epic_branch or f"epic/{today_slug()}-{self.feature_id}-{branch_suffix}"
        return PipelineFeature(
            feature_id=self.feature_id,
            title=self.title,
            risk_level=self.risk_level,
            issue_number=self.issue_number,
            issue_url=self.issue_url,
            run_id=self.run_id,
            epic_branch=branch,
            current_stage=self.current_stage,
            created_at=self.created_at,
        )


@dataclass(frozen=True)
class AutoMergeDecision:
    """Result of risk classification for unattended main merge."""

    eligible_for_auto_main_merge: bool
    requires_manual_approval: bool
    risk_level: str
    changed_files: list[str]
    restricted_files: list[str]
    unsafe_files: list[str]
    safe_files: list[str]
    reasons: list[str]


@dataclass(frozen=True)
class GateCheckResult:
    """Report presence gate result."""

    passed: bool
    feature_id: str
    checked_stages: list[str]
    missing: dict[str, list[str]]
    found: dict[str, list[str]]
    reasons: list[str]
    invalid: dict[str, list[str]] = field(default_factory=dict)


def today_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def normalize_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


# Canonical gate decision vocabulary.
# Codex review gate : APPROVED, APPROVED_WITH_NOTES, CHANGES_REQUESTED, BLOCKED
# Acceptance gate    : ACCEPTED, ACCEPTED_WITH_NOTES, CHANGES_REQUESTED, BLOCKED
_GATE_DECISION_MAP: dict[str, str] = {
    "accepted": "ACCEPTED",
    "accepted_with_notes": "ACCEPTED_WITH_NOTES",
    "accepted-with-notes": "ACCEPTED_WITH_NOTES",
    "changes_requested": "CHANGES_REQUESTED",
    "changes-requested": "CHANGES_REQUESTED",
    "blocked": "BLOCKED",
    "approved": "APPROVED",
    "approved_with_notes": "APPROVED_WITH_NOTES",
    "approved-with-notes": "APPROVED_WITH_NOTES",
}


def normalize_gate_decision(value: str | None) -> str | None:
    """Normalize a raw decision string to uppercase canonical form.

    Returns ``None`` for unknown or empty values so callers can distinguish
    ``not-yet-set`` from ``explicitly-accepted``.
    """
    if not value or not isinstance(value, str):
        return None
    key = value.strip().replace(" ", "_").lower()
    return _GATE_DECISION_MAP.get(key, None)


def slugify_feature(text: str, *, max_length: int = 48) -> str:
    """Create a branch-safe feature slug from an issue title or user text."""
    text = text.strip().lower()
    text = re.sub(r"^\[[^\]]+\]\s*", "", text)
    # Strip non-ASCII (including Chinese) to avoid encoding issues on Windows runners
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-") or "agent-feature"
    return text[:max_length].strip("-") or "agent-feature"


def is_restricted_path(path: str) -> bool:
    p = normalize_path(path)
    lower = p.lower()
    if any(lower.startswith(prefix.lower()) for prefix in RESTRICTED_PATH_PREFIXES):
        return True
    return any(token in lower for token in RESTRICTED_PATH_CONTAINS)


def is_safe_auto_path(path: str) -> bool:
    p = normalize_path(path)
    lower = p.lower()
    return any(lower.startswith(prefix.lower()) for prefix in SAFE_AUTO_MAIN_PREFIXES)


def classify_changed_files(changed_files: Iterable[str]) -> AutoMergeDecision:
    """Classify changed files for Level 3 auto main merge.

    The function is deliberately conservative: every changed file must be in a
    safe prefix and no changed file may match a restricted trading path.
    """
    files = [normalize_path(f) for f in changed_files if normalize_path(f)]
    restricted = [f for f in files if is_restricted_path(f)]
    safe = [f for f in files if is_safe_auto_path(f)]
    unsafe = [f for f in files if f not in safe and f not in restricted]

    reasons: list[str] = []
    if not files:
        reasons.append("no_changed_files_detected")
    if restricted:
        reasons.append("restricted_trading_or_secret_paths_touched")
    if unsafe:
        reasons.append("changed_files_outside_auto_merge_allowlist")

    eligible = bool(files) and not restricted and not unsafe
    requires_manual = not eligible
    risk_level = "safe-auto-main" if eligible else "manual-main-approval"

    return AutoMergeDecision(
        eligible_for_auto_main_merge=eligible,
        requires_manual_approval=requires_manual,
        risk_level=risk_level,
        changed_files=files,
        restricted_files=restricted,
        unsafe_files=unsafe,
        safe_files=safe,
        reasons=reasons or ["all_changed_files_match_auto_merge_allowlist"],
    )


def build_feature_state(
    *,
    title: str,
    feature_id: str | None = None,
    risk_level: str = "unknown",
    issue_number: int | None = None,
    issue_url: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    feature = PipelineFeature(
        feature_id=feature_id or slugify_feature(title),
        title=title,
        risk_level=risk_level,
        issue_number=issue_number,
        issue_url=issue_url,
        run_id=run_id,
    ).with_default_branch()
    state = asdict(feature)
    state["required_docs"] = {
        "requirements": f"docs/requirements/{today_slug()}-{feature.feature_id}-requirements.md",
        "architecture": f"docs/design/{today_slug()}-{feature.feature_id}-architecture.md",
        "team_plan": f"docs/dev_plans/{today_slug()}-{feature.feature_id}-team-plan.md",
        "phase_dev_report_pattern": (
            f"docs/dev_reports/{today_slug()}-{feature.feature_id}-phase-<n>-dev-report.md"
        ),
        "phase_test_report_pattern": (
            f"docs/test_reports/{today_slug()}-{feature.feature_id}-phase-<n>-test-report.md"
        ),
        "claude_lead_review": (
            f"docs/review/{today_slug()}-{feature.feature_id}-opencode-lead-review.md"
        ),
        "codex_review": f"docs/review/{today_slug()}-{feature.feature_id}-codex-review-r1.md",
        "acceptance": f"docs/acceptance/{today_slug()}-{feature.feature_id}-acceptance.md",
        "user_guide": f"docs/user_guides/{today_slug()}-{feature.feature_id}-user-guide.md",
        "postmortem": f"docs/postmortems/{today_slug()}-{feature.feature_id}-r3-failure.md",
    }
    state["team_pipeline"] = {
        "mode": "opencode_lead_claude_dev_opencode_test",
        "default_team_id": "hybrid-team-a",
        "max_parallel_teams": 3,
        "max_codex_review_attempts": 3,
        "current_phase": 1,
        "all_phases_tested": False,
        "codex_review_attempts": 0,
    }
    state["agent_roles"] = {
        "codex_a": ["pm", "acceptance"],
        "codex_b": ["architecture", "codex_review"],
        "opencode_lead": ["team_plan", "team_lead_review", "team_performance"],
        "claude_developer": ["phase_dev", "bugfix"],
        "opencode_tester": ["phase_test"],
    }
    state["manual_approval_required_for"] = [
        "restricted-module",
        "live-trading",
        "risk-policy-change",
        "execution-policy-change",
        "main-merge-when-auto-merge-gate-fails",
        "codex-review-fails-three-times",
    ]
    state["stage_status"] = {stage: "pending" for stage in STAGE_ORDER}
    state["stage_status"]["pm"] = "pending"
    return state


def set_pr_metadata(
    root: Path,
    *,
    pr_number: int,
    pr_url: str,
    epic_branch: str | None = None,
) -> dict[str, Any]:
    """Persist the confirmed GitHub PR identity into pipeline state files."""
    state = read_state(root)
    state["pr_number"] = pr_number
    state["pr_url"] = pr_url
    state["pull_request"] = {
        "number": pr_number,
        "url": pr_url,
    }
    if epic_branch:
        state["epic_branch"] = epic_branch
        state["pull_request"]["head_ref"] = epic_branch
    write_json(root / STATE_PATH, state)
    (root / CURRENT_TASK_PATH).write_text(
        yaml.safe_dump(state, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return state


def write_feature_state(root: Path, state: dict[str, Any]) -> None:
    agent_dir = root / PIPELINE_ROOT
    (agent_dir / "gates").mkdir(parents=True, exist_ok=True)
    (agent_dir / "handoff").mkdir(parents=True, exist_ok=True)
    write_json(root / STATE_PATH, state)
    (root / CURRENT_TASK_PATH).write_text(yaml.safe_dump(state, allow_unicode=True, sort_keys=False), encoding="utf-8")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_state(root: Path) -> dict[str, Any]:
    state_file = root / STATE_PATH
    if state_file.exists():
        return json.loads(state_file.read_text(encoding="utf-8"))
    task_file = root / CURRENT_TASK_PATH
    if task_file.exists():
        return yaml.safe_load(task_file.read_text(encoding="utf-8")) or {}
    return {}


def check_required_reports(
    root: Path,
    *,
    feature_id: str,
    through_stage: str = "acceptance",
) -> GateCheckResult:
    through_stage = LEGACY_STAGE_ALIASES.get(through_stage, through_stage)
    if through_stage not in STAGE_ORDER:
        raise ValueError(f"unknown stage: {through_stage}")
    target_index = STAGE_ORDER.index(through_stage)
    stages = list(STAGE_ORDER[: target_index + 1])
    missing: dict[str, list[str]] = {}
    found: dict[str, list[str]] = {}
    invalid: dict[str, list[str]] = {}

    for stage in stages:
        patterns = REPORT_GLOBS_BY_STAGE[stage]
        stage_found: list[str] = []
        for pattern in patterns:
            resolved_pattern = pattern.format(feature_id=feature_id)
            matches = sorted(str(path.relative_to(root)) for path in root.glob(resolved_pattern))
            stage_found.extend(matches)
        if stage_found:
            found[stage] = stage_found
            stage_invalid = _validate_stage_reports(root, stage=stage, paths=stage_found, feature_id=feature_id)
            if stage_invalid:
                invalid[stage] = stage_invalid
        else:
            missing[stage] = [pattern.format(feature_id=feature_id) for pattern in patterns]

    passed = not missing and not invalid
    reasons: list[str] = []
    if missing:
        reasons.append("missing_required_stage_reports")
    if invalid:
        reasons.append("invalid_required_stage_reports")
    if passed:
        reasons.append("all_required_reports_found")
    return GateCheckResult(
        passed=passed,
        feature_id=feature_id,
        checked_stages=stages,
        missing=missing,
        found=found,
        invalid=invalid,
        reasons=reasons,
    )


def _validate_stage_reports(
    root: Path,
    *,
    stage: str,
    paths: list[str],
    feature_id: str,
) -> list[str]:
    """Validate content-sensitive gate artifacts for early Codex stages."""
    if stage not in {"pm", "architecture"}:
        return []

    invalid: list[str] = []
    for rel_path in paths:
        path = root / rel_path
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            invalid.append(f"{rel_path}:unreadable:{exc.__class__.__name__}")
            continue
        errors = _validate_pm_report(text, feature_id) if stage == "pm" else _validate_architecture_report(text, feature_id)
        invalid.extend(f"{rel_path}:{error}" for error in errors)
    return invalid


def _validate_pm_report(text: str, feature_id: str) -> list[str]:
    errors = _validate_common_markdown_artifact(text)
    required_patterns = [
        rf"(?m)^#\s+{re.escape(feature_id)}\s+Requirements\s*$",
        r"(?m)^##\s+User Goal\s*$",
        r"(?m)^##\s+Functional Requirements\s*$",
        r"(?m)^##\s+Acceptance Criteria\s*$",
        r"(?m)^##\s+Safety Constraints\s*$",
    ]
    for pattern in required_patterns:
        if not re.search(pattern, text):
            errors.append(f"missing_required_heading:{pattern}")
    return errors


def _validate_architecture_report(text: str, feature_id: str) -> list[str]:
    errors = _validate_common_markdown_artifact(text)
    if not re.search(rf"(?m)^#\s+{re.escape(feature_id)}\s+(Architecture|Design)\s*$", text):
        errors.append("missing_architecture_title")
    required_patterns = [
        r"(?m)^##\s+Architecture Summary\s*$",
        r"(?m)^##\s+Module Plan\s*$",
        r"(?m)^##\s+Technical Decisions\s*$",
        r"(?m)^##\s+Safety Impact\s*$",
        r"(?m)^##\s+Development Guidance\s*$",
    ]
    for pattern in required_patterns:
        if not re.search(pattern, text):
            errors.append(f"missing_required_heading:{pattern}")
    section_count = len(re.findall(r"(?m)^##\s+\S", text))
    if section_count < 3:
        errors.append("architecture_has_too_few_sections")
    log_only_markers = re.findall(
        r"(?mi)^(Using Codex|Running Codex|Codex WSL exit|STDOUT:|STDERR:|OUTPUT_FILE:|Process completed|ERROR:)",
        text,
    )
    if log_only_markers and section_count < 3:
        errors.append("architecture_looks_log_only")
    return errors


def _validate_common_markdown_artifact(text: str) -> list[str]:
    errors: list[str] = []
    if not text.strip():
        errors.append("artifact_empty")
    if "$($EventArgs.Data)" in text:
        errors.append("artifact_contains_literal_eventargs_data")
    return errors



# ---------------------------------------------------------------------------
# Pipeline state / gate consistency
# ---------------------------------------------------------------------------

# Full stage progression including post-acceptance gates.
# pm / architecture / team_plan do NOT have standalone gate files — they are
# inferred as "passed" when any downstream gated stage has evidence.
FULL_STAGE_ORDER: tuple[str, ...] = (
    "pm",
    "architecture",
    "team_plan",
    "phase_dev",
    "phase_test",
    "claude_lead_review",
    "codex_review",
    "acceptance",
    "merge_gate",
    "manual_approval_required",
)

# Stages that have standalone gate JSON files.
STAGES_WITH_GATES: tuple[str, ...] = (
    "phase_dev",
    "phase_test",
    "claude_lead_review",
    "codex_review",
    "acceptance",
)

GATE_FILES_BY_STAGE: dict[str, list[str]] = {
    "phase_dev": ["phase_dev_gate.json"],
    "phase_test": ["phase_test_gate.json"],
    "claude_lead_review": ["claude_lead_review_gate.json"],
    "codex_review": ["codex_review_gate.json"],
    "acceptance": ["acceptance_gate.json"],
}

GATES_DIR = PIPELINE_ROOT / "gates"


def _read_gate(root: Path, gate_name: str) -> dict[str, Any] | None:
    """Read a single gate JSON, return None if missing or unparseable."""
    path = root / GATES_DIR / gate_name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _infer_passed_stages_from_gates(root: Path) -> dict[str, bool]:
    """Infer which pipeline stages have passed based on gate evidence.

    Stages that have a gate file (phase_dev … acceptance) are checked
    directly.  Stages *before* the first gated stage (pm, architecture,
    team_plan) are considered implicitly passed when any gated stage
    has evidence — because the pipeline must have advanced through them
    to reach a downstream gated stage.

    Returns a dict with entries for ALL stages in FULL_STAGE_ORDER:
      key → True  when the stage has passed (explicitly or implicitly)
      key → False when the stage has NOT passed
    """
    # Check explicit gate files
    explicit: dict[str, bool] = {}
    for stage_key, gate_names in GATE_FILES_BY_STAGE.items():
        for gname in gate_names:
            gate = _read_gate(root, gname)
            if gate is not None and gate.get("passed") is True and gate.get("found"):
                explicit[stage_key] = True
                break
        else:
            explicit[stage_key] = False

    # Find the last explicitly-passed gated stage
    last_passed_idx = -1
    for stage_key in STAGES_WITH_GATES:
        if explicit.get(stage_key):
            last_passed_idx = max(last_passed_idx, FULL_STAGE_ORDER.index(stage_key))

    # Build result for ALL stages
    result: dict[str, bool] = {}
    for idx, stage in enumerate(FULL_STAGE_ORDER):
        if stage in STAGES_WITH_GATES:
            # Explicit gate check
            result[stage] = explicit.get(stage, False)
        elif idx < FULL_STAGE_ORDER.index("phase_dev"):
            # Pre-gate stages (pm, architecture, team_plan):
            # passed if ANY downstream gated stage has passed
            result[stage] = last_passed_idx >= 0
        else:
            # Post-acceptance stages (merge_gate, manual_approval_required) —
            # not inferred from pipeline gates; start as False here
            result[stage] = False

    return result


def _find_latest_active_stage(passed_stages: dict[str, bool]) -> str:
    """Return the first FULL_STAGE_ORDER stage that has NOT passed.

    When ALL stages up to ``acceptance`` have passed, the next expected
    stage is ``merge_gate_pending`` (or ``manual_approval_required``
    if the auto_merge_gate file already demands manual approval).
    """
    for stage in FULL_STAGE_ORDER:
        if not passed_stages.get(stage):
            return stage
    return FULL_STAGE_ORDER[-1]


def _check_auto_merge_gate(root: Path) -> bool:
    """Return True if auto_merge_gate.json exists and requires manual approval."""
    gate = _read_gate(root, "auto_merge_gate.json")
    if gate is None:
        return False
    return gate.get("requires_manual_approval", False)


def check_state_gate_consistency(root: Path) -> dict[str, Any]:
    """Compare .agent/state.json / .agent/current_task.yaml with gate evidence.

    Returns a diagnostics dict with:
    - consistent (bool)
    - issues (list of strings)
    - passed_stages (dict)
    - stale_fields (dict of current values vs expected)
    """
    state = read_state(root)
    passed_stages = _infer_passed_stages_from_gates(root)
    requires_manual = _check_auto_merge_gate(root)
    issues: list[str] = []
    stale: dict[str, Any] = {}

    # 1. Compare stage_status entries
    stage_status = state.get("stage_status", {})
    for stage_key, is_passed in passed_stages.items():
        if stage_key not in STAGES_WITH_GATES:
            continue  # only check stages that have explicit gate files
        current = stage_status.get(stage_key, "unknown")
        if is_passed and current != "passed":
            issues.append(f"stage_status.{stage_key}: gate=passed but state={current!r}")
            stale[f"stage_status.{stage_key}"] = {"current": current, "expected": "passed"}

    # 2. Compare current_stage
    expected_stage = _find_latest_active_stage(passed_stages)

    # Override to manual_approval_required if auto_merge_gate demands it
    if requires_manual and expected_stage == "merge_gate":
        expected_stage = "manual_approval_required"

    expected_pending = f"{expected_stage}_pending"
    current_stage = state.get("current_stage", "")

    if current_stage != expected_pending and any(
        v for k, v in passed_stages.items() if k in STAGES_WITH_GATES
    ):
        issues.append(
            f"current_stage: state={current_stage!r} but gates imply {expected_pending!r}"
        )
        stale["current_stage"] = {"current": current_stage, "expected": expected_pending}

    # 3. team_pipeline.all_phases_tested
    tp = state.get("team_pipeline", {})
    phases_tested = tp.get("all_phases_tested", False)
    pt_passed = passed_stages.get("phase_test", False)
    if pt_passed and not phases_tested:
        issues.append(
            "team_pipeline.all_phases_tested: gate phase_test passed but state is false"
        )
        stale["team_pipeline.all_phases_tested"] = {"current": phases_tested, "expected": True}
    if not pt_passed and phases_tested:
        issues.append(
            "team_pipeline.all_phases_tested: gate phase_test not passed but state is true"
        )

    return {
        "consistent": len(issues) == 0,
        "issues": issues,
        "passed_stages": passed_stages,
        "stale_fields": stale,
    }


def sync_state_from_gates(root: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """Update .agent/state.json and .agent/current_task.yaml from gate truth.

    Returns a report dict with:
    - updated (bool)
    - changes_made (list of strings)
    - diagnostics (from check_state_gate_consistency)
    """
    diagnostics = check_state_gate_consistency(root)
    state = read_state(root)

    if diagnostics["consistent"]:
        return {"updated": False, "changes_made": [], "diagnostics": diagnostics}

    changes: list[str] = []
    state = dict(state)  # mutable copy
    passed_stages = diagnostics["passed_stages"]
    requires_manual = _check_auto_merge_gate(root)

    # 1. Update stage_status for gated stages only
    stage_status = dict(state.get("stage_status", {}))
    for stage_key in STAGES_WITH_GATES:
        if passed_stages.get(stage_key) and stage_status.get(stage_key, "") != "passed":
            stage_status[stage_key] = "passed"
            changes.append(f"stage_status.{stage_key} \u2192 passed")
    state["stage_status"] = stage_status

    # 2. Update current_stage
    expected_stage = _find_latest_active_stage(passed_stages)
    if requires_manual and expected_stage == "merge_gate":
        expected_stage = "manual_approval_required"
    expected_pending = f"{expected_stage}_pending"

    current_stage = state.get("current_stage", "")
    if current_stage != expected_pending:
        old_display = current_stage if current_stage else "(unset)"
        state["current_stage"] = expected_pending
        changes.append(f"current_stage {old_display} \u2192 {expected_pending!r}")

    # 3. Update team_pipeline.all_phases_tested
    tp = dict(state.get("team_pipeline", {}))
    pt_passed = passed_stages.get("phase_test", False)
    if pt_passed and not tp.get("all_phases_tested", False):
        tp["all_phases_tested"] = True
        changes.append("team_pipeline.all_phases_tested \u2192 true")
    state["team_pipeline"] = tp

    if not changes:
        return {"updated": False, "changes_made": [], "diagnostics": diagnostics}

    if not dry_run:
        write_json(root / STATE_PATH, state)
        (root / CURRENT_TASK_PATH).write_text(
            yaml.safe_dump(state, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )

    return {
        "updated": True,
        "changes_made": changes,
        "diagnostics": diagnostics,
    }

def render_handoff_prompt(stage: str, state: dict[str, Any]) -> str:
    legacy_stage_map = {
        "pm_architect": "codex_pm",
        "developer": "claude_developer",
        "tester": "claude_tester",
        "reviewer": "codex_reviewer",
        "acceptance": "codex_acceptance",
    }
    stage = legacy_stage_map.get(stage, stage)
    feature_id = state.get("feature_id", "unknown-feature")
    title = state.get("title", feature_id)
    docs = state.get("required_docs", {})
    branch = state.get("epic_branch", "epic/<date-feature>")
    team = state.get("team_pipeline", {})
    max_attempts = team.get("max_codex_review_attempts", 3)

    common = f"""# Agent Handoff: {stage}\n\nFeature: {feature_id}\nTitle: {title}\nEpic branch: {branch}\nRisk level: {state.get('risk_level', 'unknown')}\n\nRequired read order:\n1. AGENTS.md\n2. docs/process/AGENT_DEVELOPMENT_PIPELINE.md\n3. docs/process/BRANCH_WORKFLOW.md\n4. docs/pipeline/AGENT_AUTOMATION_ARCHITECTURE.md\n5. docs/pipeline/AUTO_MERGE_POLICY.md\n"""

    if stage == "codex_pm":
        return common + f"""\nTask:\n- Act as Codex A, the PM Agent.\n- Produce the PM requirements document at `{docs.get('requirements', '<requirements-doc>')}`.\n- Include goals, non-goals, feature list, acceptance criteria, safety constraints, and user-facing success criteria.\n- Do not write architecture or product code in this stage.\n"""
    if stage == "codex_architect":
        return common + f"""\nTask:\n- Read the requirements document at `{docs.get('requirements', '<requirements-doc>')}`.\n- Produce the architecture design at `{docs.get('architecture', '<architecture-doc>')}`.\n- Include module boundaries, phase slices, technical choices, pseudocode, test strategy, and handoff guidance for OpenCode Lead / Claude Developer / OpenCode Tester.\n- Do not write product code in this stage.\n"""
    if stage == "claude_lead_plan":
        return common + f"""\nTask:\n- Compatibility stage ID: `claude_lead_plan`; actual role: OpenCode Team Leader.\n- Runtime is fixed to `opencode-go/glm-5.2` and must use superpowers.\n- Read `{docs.get('architecture', '<architecture-doc>')}` and split implementation into ordered phases.\n- Produce `{docs.get('team_plan', '<team-plan>')}`.\n- Each phase must have scope, owner, branch, self-test commands, tester checks, and release criteria.\n- After each phase test passes, route back to Claude Code Developer for the next phase until all phases are complete.\n"""
    if stage == "claude_developer":
        return common + f"""\nTask:\n- Compatibility stage ID: `claude_developer`; actual role: Claude Code Developer.\n- Runtime is fixed to `ultracode-xhigh`, `effort=xhigh`, feature-dev workflow, and superpowers.\n- Implement only the current phase from `{docs.get('team_plan', '<team-plan>')}`.\n- In GitHub Stage Runner mode, remain on the checked-out PR branch and let the workflow commit/push; in manual mode follow `docs/process/BRANCH_WORKFLOW.md`.\n- Write focused failing tests first where practical.\n- Produce `{docs.get('phase_dev_report_pattern', '<phase-dev-report>')}` with exact self-test commands.\n- After OpenCode Test Engineer verifies the phase, continue with the next planned phase until all phases are tested.\n- Do not touch restricted trading modules unless the architecture document explicitly permits it.\n"""
    if stage == "claude_tester":
        return common + f"""\nTask:\n- Compatibility stage ID: `claude_tester`; actual role: OpenCode Test Engineer.\n- Runtime is fixed to `opencode-go/deepseek-v4-pro`, `variant=max`, and superpowers.\n- Create a temporary local `test/{feature_id}/phase-<n>-tester-<timestamp>` branch from the phase branch under test.\n- Verify the requirements, architecture, team plan, phase dev report, and diff.\n- Use verification-before-completion; use systematic-debugging for failures.\n- Return to the original branch, delete the temporary test branch, and produce `{docs.get('phase_test_report_pattern', '<phase-test-report>')}` without changing business code on the original branch.\n- If the phase passes, route back to Claude Code Developer for the next phase unless all phases are complete.\n- Generate `feedback/bugs/open/BUG_*.md` and `.json` for reproducible blockers.\n"""
    if stage == "claude_lead_review":
        return common + f"""\nTask:\n- Compatibility stage ID: `claude_lead_review`; actual role: OpenCode Team Leader Reviewer.\n- Runtime is fixed to `opencode-go/glm-5.2` and must use superpowers.\n- Review all phase development reports and test reports.\n- Confirm every planned phase is complete and tested before handing off to Codex B.\n- Produce `{docs.get('claude_lead_review', '<opencode-lead-review>')}`.\n- If any phase is incomplete, route back to Claude Code Developer / OpenCode Test Engineer instead of escalating to Codex B.\n"""
    if stage == "codex_reviewer":
        return common + f"""\nTask:\n- Act as Codex B, the final Architect Reviewer.\n- Review code only after `{docs.get('claude_lead_review', '<opencode-lead-review>')}` confirms all phases passed.\n- Produce `{docs.get('codex_review', '<codex-review>')}`.\n- Conclusion must be APPROVED, APPROVED_WITH_NOTES, CHANGES_REQUESTED, or BLOCKED.\n- If review fails, return structured feedback to OpenCode Team Leader. After {max_attempts} failed Codex reviews, trigger the team incompetence alert and postmortem gate.\n"""
    if stage == "codex_acceptance":
        return common + f"""\nTask:\n- Perform PM acceptance from the user perspective.\n- Produce `{docs.get('acceptance', '<acceptance-report>')}`.\n- Conclusion must be one of: ACCEPTED, ACCEPTED_WITH_NOTES, CHANGES_REQUESTED, BLOCKED.\n- ACCEPTED_WITH_NOTES is acceptable only for non-blocking notes.\n- CHANGES_REQUESTED or BLOCKED must fail the acceptance gate.\n"""
    if stage == "bugfix":
        return common + """\nTask:\n- Read the test/review/acceptance failure report and feedback bugs.\n- Work in an isolated `bugfix/<bug-id>-<timestamp>` branch/worktree.\n- Add regression tests before fixing.\n- Do not merge to main without the merge gate.\n"""
    if stage == "postmortem":
        return common + f"""\nTask:\n- Codex B has rejected this feature `{max_attempts}` times.\n- Stop normal development and produce `{docs.get('postmortem', '<postmortem>')}`.\n- Include root causes, missed gates, responsible stage, corrective actions, and workflow improvement proposals.\n- The user must approve resuming the pipeline.\n"""
    raise ValueError(f"unknown handoff stage: {stage}")


def write_handoff(root: Path, stage: str, state: dict[str, Any] | None = None) -> Path:
    payload = state if state is not None else read_state(root)
    if not payload:
        raise RuntimeError("pipeline state is missing; run init-feature first")
    text = render_handoff_prompt(stage, payload)
    path = root / PIPELINE_ROOT / "handoff" / f"{stage}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
