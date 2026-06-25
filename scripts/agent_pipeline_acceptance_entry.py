#!/usr/bin/env python
"""Build a PR-visible user acceptance entry from committed pipeline evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import quote


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _blob_url(repository: str, ref: str, path: str) -> str:
    encoded_ref = quote(ref, safe="")
    encoded_path = quote(path.replace("\\", "/"), safe="/")
    return f"https://github.com/{repository}/blob/{encoded_ref}/{encoded_path}"


def _latest(root: Path, pattern: str) -> str:
    matches = sorted(root.glob(pattern))
    return str(matches[-1].relative_to(root)).replace("\\", "/") if matches else ""


def build_acceptance_entry(
    root: Path,
    *,
    repository: str,
    ref: str,
    actions_url: str,
) -> str:
    state = _read_json(root / ".agent" / "state.json")
    gate = _read_json(root / ".agent" / "gates" / "acceptance_gate.json")
    feature_id = str(state.get("feature_id") or "unknown-feature")
    issue_number = state.get("issue_number")
    current_phase = int(state.get("team_pipeline", {}).get("current_phase", 1))
    acceptance = str(gate.get("acceptance_artifact") or "").replace("\\", "/")
    if not acceptance:
        acceptance = _latest(root, f"docs/acceptance/*-{feature_id}-acceptance.md")
    phase_test = _latest(
        root,
        f"docs/test_reports/*-{feature_id}*phase-{current_phase}-test-report*.md",
    )
    codex_review = _latest(root, f"docs/review/*-{feature_id}*codex-review*.md")
    user_guide = _latest(root, f"docs/user_guides/*-{feature_id}*user-guide.md")
    decision = str(gate.get("decision") or "UNKNOWN")

    links = [
        ("中文验收报告", acceptance),
        (f"Phase {current_phase} 测试报告", phase_test),
        ("Codex Review", codex_review),
        ("用户指南", user_guide),
    ]
    link_lines = [
        f"- [{label}]({_blob_url(repository, ref, path)})"
        for label, path in links
        if path
    ]
    api_lines = [
        f"- API：`GET /product/agentops/pipelines/{feature_id}`",
    ]
    if issue_number:
        api_lines.append(
            f"- API：`GET /product/agentops/pipelines/by-issue/{issue_number}`"
        )
    api_lines.append("- UI：运行 `python main.py dashboard`，打开 AgentOps Control Tower")
    if actions_url:
        link_lines.append(f"- [最终 Merge Gate 与 Dashboard artifact]({actions_url})")

    return "\n".join(
        [
            "<!-- agent-user-acceptance:start -->",
            "## 用户验收入口",
            "",
            f"**Pipeline 验收结论：`{decision}`**",
            "",
            "### 验收材料",
            "",
            *link_lines,
            "",
            "### 功能入口",
            "",
            *api_lines,
            "",
            "main 不会自动合并。请阅读验收报告和非阻断备注后人工决定是否合并。",
            "<!-- agent-user-acceptance:end -->",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--actions-url", default="")
    parser.add_argument("--output")
    args = parser.parse_args()
    text = build_acceptance_entry(
        Path(args.root).resolve(),
        repository=args.repository,
        ref=args.ref,
        actions_url=args.actions_url,
    )
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
