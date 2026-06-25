from pathlib import Path

from scripts.agent_pipeline_acceptance_entry import build_acceptance_entry
from src.product_app.agent_pipeline_automation import write_json


def test_build_acceptance_entry_exposes_user_verification_links(tmp_path: Path):
    feature_id = "agentops"
    write_json(
        tmp_path / ".agent/state.json",
        {
            "feature_id": feature_id,
            "issue_number": 75,
            "team_pipeline": {"current_phase": 5},
        },
    )
    acceptance = "docs/acceptance/2026-06-25-agentops-acceptance.md"
    write_json(
        tmp_path / ".agent/gates/acceptance_gate.json",
        {
            "passed": True,
            "decision": "ACCEPTED_WITH_NOTES",
            "acceptance_artifact": acceptance,
        },
    )
    for path in (
        acceptance,
        "docs/test_reports/2026-06-25-agentops-phase-5-test-report.md",
        "docs/review/2026-06-25-agentops-codex-review-r1.md",
        "docs/user_guides/2026-06-25-agentops-user-guide.md",
    ):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# evidence\n", encoding="utf-8")

    result = build_acceptance_entry(
        tmp_path,
        repository="owner/repo",
        ref="abc123",
        actions_url="https://github.com/owner/repo/actions/runs/1",
    )

    assert "用户验收入口" in result
    assert "ACCEPTED_WITH_NOTES" in result
    assert "docs/acceptance/2026-06-25-agentops-acceptance.md" in result
    assert "GET /product/agentops/pipelines/agentops" in result
    assert "GET /product/agentops/pipelines/by-issue/75" in result
    assert "python main.py dashboard" in result
    assert "actions/runs/1" in result
