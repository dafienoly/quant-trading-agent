#!/usr/bin/env python
"""CLI for issue-driven Agent pipeline state, handoff, and merge gates."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.product_app.agent_pipeline_automation import (  # noqa: E402
    AUTO_MERGE_GATE_PATH,
    advance_after_phase_test,
    build_feature_state,
    check_required_reports,
    check_state_gate_consistency,
    classify_changed_files,
    normalize_gate_decision,
    read_state,
    register_stage_failure,
    set_pr_metadata,
    sync_team_plan_metadata,
    sync_state_from_gates,
    validate_stage_delivery,
    write_feature_state,
    write_handoff,
    write_json,
)


def _repo_root() -> Path:
    return Path(os.getenv("GITHUB_WORKSPACE", ".")).resolve()


def _read_lines(path: str | None) -> list[str]:
    if not path:
        return []
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(path)
    return [line.strip() for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def cmd_init_feature(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    state = build_feature_state(
        title=args.title,
        feature_id=args.feature_id,
        risk_level=args.risk_level,
        issue_number=args.issue_number,
        issue_url=args.issue_url,
        run_id=args.run_id,
    )
    write_feature_state(root, state)
    for stage in args.handoff_stage:
        write_handoff(root, stage, state)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def cmd_classify_changes(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    files = list(args.changed_file or []) + _read_lines(args.changed_files_file)
    decision = classify_changed_files(files)
    payload = decision.__dict__
    output = root / (args.output or AUTO_MERGE_GATE_PATH)
    write_json(output, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.fail_on_manual_approval and decision.requires_manual_approval:
        return 2
    return 0


def cmd_check_gates(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    state = read_state(root)
    feature_id = args.feature_id or state.get("feature_id")
    if not feature_id:
        print("feature_id is required when pipeline state is missing", file=sys.stderr)
        return 2
    result = check_required_reports(root, feature_id=feature_id, through_stage=args.through_stage)
    payload = result.__dict__
    stage_decision = result.decisions.get(args.through_stage)
    if stage_decision:
        payload["decision"] = stage_decision
    route_back = {
        "phase_dev": "claude_developer",
        "phase_test": "claude_developer",
        "claude_lead_review": "claude_developer",
        "codex_review": "claude_lead_review",
        "acceptance": "claude_developer",
    }
    if not result.passed and args.through_stage in route_back:
        payload["route_back_to"] = route_back[args.through_stage]
    # Preserve decision / acceptance_artifact from an existing gate file
    # (written by the real Codex acceptance wrapper) so the gate metadata
    # is not overwritten by the glob-based check.
    gate_path = root / ".agent" / "gates" / f"{args.through_stage}_gate.json"
    if gate_path.exists():
        try:
            existing = json.loads(gate_path.read_text(encoding="utf-8"))
            raw_decision = existing.get("decision")
            if raw_decision and not stage_decision:
                normalized = normalize_gate_decision(raw_decision)
                payload["decision"] = normalized if normalized else raw_decision
            if existing.get("acceptance_artifact"):
                payload["acceptance_artifact"] = existing["acceptance_artifact"]
        except (json.JSONDecodeError, OSError):
            pass
    write_json(gate_path, payload)
    if result.passed and args.through_stage == "team_plan":
        sync_team_plan_metadata(root, feature_id=feature_id)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.passed else 2


def cmd_validate_stage_delivery(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    result = validate_stage_delivery(
        root,
        stage=args.stage,
        changed_files=_read_lines(args.changed_files_file)
        if args.changed_files_file
        else None,
    )
    payload = result.__dict__
    gate_path = root / ".agent" / "gates" / "phase_dev_delivery_gate.json"
    write_json(gate_path, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.passed else 2


def cmd_advance_phase(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    result = advance_after_phase_test(root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("advanced") else 2


def cmd_register_stage_failure(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    result = register_stage_failure(root, stage=args.stage)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_write_handoff(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    path = write_handoff(root, args.stage)
    print(str(path))
    return 0


def cmd_print_state(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    state = read_state(root)
    if args.key:
        value = state
        for part in args.key.split("."):
            if not isinstance(value, dict) or part not in value:
                return 2
            value = value[part]
        print(value)
    else:
        print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def cmd_check_state_gate_consistency(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    result = check_state_gate_consistency(root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["consistent"] else 2


def cmd_sync_state_from_gates(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    result = sync_state_from_gates(root, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("updated") and not args.dry_run:
        # Re-check consistency AFTER the sync to get accurate diagnostics
        from src.product_app.agent_pipeline_automation import check_state_gate_consistency
        after = check_state_gate_consistency(root)
        return 0 if after["consistent"] else 2
    return 0 if not result.get("updated") or result["diagnostics"]["consistent"] else 2


def cmd_set_pr_metadata(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    state = set_pr_metadata(
        root,
        pr_number=args.pr_number,
        pr_url=args.pr_url,
        epic_branch=args.epic_branch,
    )
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agent pipeline automation CLI")
    parser.set_defaults(func=None)

    common_root = argparse.ArgumentParser(add_help=False)
    common_root.add_argument("--root", default=str(_repo_root()))

    init = parser.add_subparsers(dest="command")

    p = init.add_parser("init-feature", parents=[common_root])
    p.add_argument("--title", required=True)
    p.add_argument("--feature-id")
    p.add_argument("--risk-level", default="unknown")
    p.add_argument("--issue-number", type=int)
    p.add_argument("--issue-url")
    p.add_argument("--run-id")
    p.add_argument(
        "--handoff-stage",
        action="append",
        default=["codex_pm"],
        choices=[
            "pm_architect",
            "codex_pm",
            "codex_architect",
            "claude_lead_plan",
            "developer",
            "claude_developer",
            "tester",
            "claude_tester",
            "claude_lead_review",
            "bugfix",
            "reviewer",
            "codex_reviewer",
            "acceptance",
            "codex_acceptance",
            "postmortem",
        ],
    )
    p.set_defaults(func=cmd_init_feature)

    p = init.add_parser("classify-changes", parents=[common_root])
    p.add_argument("--changed-file", action="append", default=[])
    p.add_argument("--changed-files-file")
    p.add_argument("--output")
    p.add_argument("--fail-on-manual-approval", action="store_true")
    p.set_defaults(func=cmd_classify_changes)

    p = init.add_parser("check-gates", parents=[common_root])
    p.add_argument("--feature-id")
    p.add_argument("--through-stage", default="acceptance")
    p.set_defaults(func=cmd_check_gates)

    p = init.add_parser("validate-stage-delivery", parents=[common_root])
    p.add_argument("--stage", required=True, choices=["claude_developer", "bugfix"])
    p.add_argument("--changed-files-file")
    p.set_defaults(func=cmd_validate_stage_delivery)

    p = init.add_parser("advance-phase", parents=[common_root])
    p.set_defaults(func=cmd_advance_phase)

    p = init.add_parser("register-stage-failure", parents=[common_root])
    p.add_argument("--stage", required=True, choices=["phase_test"])
    p.set_defaults(func=cmd_register_stage_failure)

    p = init.add_parser("write-handoff", parents=[common_root])
    p.add_argument(
        "--stage",
        required=True,
        choices=[
            "pm_architect",
            "codex_pm",
            "codex_architect",
            "claude_lead_plan",
            "developer",
            "claude_developer",
            "tester",
            "claude_tester",
            "claude_lead_review",
            "bugfix",
            "reviewer",
            "codex_reviewer",
            "acceptance",
            "codex_acceptance",
            "postmortem",
        ],
    )
    p.set_defaults(func=cmd_write_handoff)

    p = init.add_parser("print-state", parents=[common_root])
    p.add_argument("--key")
    p.set_defaults(func=cmd_print_state)

    p = init.add_parser("check-state-gate-consistency", parents=[common_root],
                        help="Check if .agent/state.json metadata is consistent with gate evidence")
    p.set_defaults(func=cmd_check_state_gate_consistency)

    p = init.add_parser("sync-state-from-gates", parents=[common_root],
                        help="Update .agent/state.json and .agent/current_task.yaml from gate truth")
    p.add_argument("--dry-run", action="store_true",
                   help="Report changes without writing")
    p.set_defaults(func=cmd_sync_state_from_gates)

    p = init.add_parser("set-pr-metadata", parents=[common_root],
                        help="Persist the confirmed pull request identity into pipeline state")
    p.add_argument("--pr-number", type=int, required=True)
    p.add_argument("--pr-url", required=True)
    p.add_argument("--epic-branch")
    p.set_defaults(func=cmd_set_pr_metadata)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.func is None:
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
