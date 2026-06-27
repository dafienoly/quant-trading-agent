from __future__ import annotations

import json
import subprocess
import sys

from src.product_app.agent_runtime import RuntimeMode, RuntimeProvider, resolve_agent_runtime


def test_codex_stage_resolves_real_when_enabled_and_command_configured():
    profile = resolve_agent_runtime(
        "codex_pm",
        env={
            "CODEX_A_PM_AGENT_COMMAND": "python scripts/run-codex-stage.py --stage codex_pm",
            "AGENT_REAL_CODEX_PM": "true",
            "AGENT_REAL_CODEX_PM_STRICT": "true",
        },
    )

    assert profile.provider == RuntimeProvider.CODEX
    assert profile.mode == RuntimeMode.REAL
    assert profile.command_configured is True
    assert profile.command_fingerprint.startswith("sha256:")
    assert "python scripts/run-codex-stage.py" not in profile.model_dump_json()
    assert profile.real_enabled is True
    assert profile.strict_enabled is True
    assert profile.safety.safe_to_execute is True


def test_codex_stage_without_command_is_disabled():
    profile = resolve_agent_runtime(
        "codex_pm",
        env={"AGENT_REAL_CODEX_PM": "false"},
    )

    assert profile.mode == RuntimeMode.DISABLED
    assert profile.command_configured is False
    assert profile.safety.safe_to_execute is False
    assert "CODEX_A_PM_AGENT_COMMAND" in profile.audit.missing_inputs


def test_strict_mode_blocks_non_real_runtime():
    profile = resolve_agent_runtime(
        "codex_pm",
        env={"AGENT_REAL_CODEX_PM_STRICT": "true"},
    )

    assert profile.mode == RuntimeMode.DISABLED
    assert profile.strict_enabled is True
    assert profile.safety.blockers == ["Strict mode requires a real runtime profile."]
    assert profile.safety.safe_to_execute is False


def test_command_with_mock_marker_resolves_mock_without_leaking_value():
    profile = resolve_agent_runtime(
        "codex_pm",
        env={
            "CODEX_A_PM_AGENT_COMMAND": "echo mock runtime command with SECRET=abc",
            "AGENT_REAL_CODEX_PM": "true",
        },
    )

    dumped = profile.model_dump_json()
    assert profile.mode == RuntimeMode.MOCK
    assert profile.command_fingerprint.startswith("sha256:")
    assert "SECRET=abc" not in dumped
    assert "echo mock runtime" not in dumped
    assert profile.safety.safe_to_execute is False


def test_dry_run_override_wins_even_when_real_command_exists():
    profile = resolve_agent_runtime(
        "codex_pm",
        env={
            "CODEX_A_PM_AGENT_COMMAND": "python real_runner.py",
            "AGENT_REAL_CODEX_PM": "true",
        },
        dry_run=True,
    )

    assert profile.mode == RuntimeMode.DRY_RUN
    assert profile.safety.safe_to_execute is False


def test_codex_reviewer_uses_fallback_command_input():
    profile = resolve_agent_runtime(
        "codex_reviewer",
        env={
            "REVIEW_AGENT_COMMAND": "python reviewer.py",
            "AGENT_REAL_CODEX_REVIEWER": "true",
        },
    )

    assert profile.command_configured is True
    assert profile.audit.configured_inputs == ["REVIEW_AGENT_COMMAND"]
    assert profile.audit.fallback_inputs == ["REVIEW_AGENT_COMMAND"]
    assert profile.mode == RuntimeMode.REAL


def test_team_stage_resolves_opencode_real_profile():
    profile = resolve_agent_runtime(
        "claude_developer",
        env={"AGENT_DEVELOPER_STAGE_TIMEOUT_SECONDS": "3600"},
    )

    assert profile.provider == RuntimeProvider.OPENCODE
    assert profile.mode == RuntimeMode.REAL
    assert profile.command_configured is True
    assert profile.timeout_seconds == 3600
    assert profile.model == "opencode-go/deepseek-v4-flash"
    assert profile.variant == "max"
    assert profile.safety.safe_to_execute is True
    assert any("legacy claude_*" in note for note in profile.audit.notes)


def test_unknown_stage_is_blocked_unknown():
    profile = resolve_agent_runtime("not_a_stage", env={})

    assert profile.provider == RuntimeProvider.UNKNOWN
    assert profile.mode == RuntimeMode.UNKNOWN
    assert profile.safety.safe_to_execute is False
    assert profile.safety.blockers == ["Runtime stage is not registered."]


def test_agent_runtime_profile_cli_outputs_secret_safe_json():
    result = subprocess.run(
        [sys.executable, "scripts/agent_runtime_profile.py", "--stage", "runtime_preflight", "--dry-run"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    payload = json.loads(result.stdout)

    assert payload["contract_version"] == "agent_runtime.profile.v1"
    assert payload["stage"] == "runtime_preflight"
    assert payload["mode"] == "dry_run"
    assert payload["safety"]["executes_command"] is False
    assert payload["safety"]["command_value_exposed"] is False
